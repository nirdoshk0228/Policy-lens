"""
Step A.2 — Section-wise chunking.

Idea: an insurance policy is already organised by its authors into sections
(Waiting Periods, Exclusions, Room Rent ...). If we cut by fixed size
(say every 500 words), one chunk might end in the middle of an exclusion
and the next chunk starts with half a sentence — retrieval gets worse.
So we cut at headings, and only split further if a section is too long.

Every chunk keeps metadata (policy, section, clause, pages) so the final
answer can cite "Section: Exclusions > Code-Excl02, page 14".
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, asdict, field

from .extract import Line

# Patterns that look like clause headings in Indian health policies:
#   "4.2 Room Rent", "C.1 In-patient Care", "Code-Excl02", "SECTION B", "PART II"
NUMBERED_RE = re.compile(r"^([A-Z]?\d+(\.\d+)*|[A-Z]\.\d+(\.\d+)*)[.)]?\s+\S")
CODE_RE = re.compile(r"^code\s*[-–]?\s*excl\s*\d+", re.IGNORECASE)
# "Section 4", "PART II", "Annexure-A" — but NOT body sentences that merely start
# with these words ("Schedule then the CB ...", "Section 56() of the Act ...").
SECTION_WORD_RE = re.compile(
    r"^(section|part|schedule|annexure)\s*[-–:]?\s*([0-9]+|[ivxlc]+|[a-z])\b(?!\()", re.IGNORECASE)
HAS_WORD_RE = re.compile(r"[A-Za-z]{2,}")


@dataclass
class Chunk:
    chunk_id: str
    policy_name: str
    section: str
    clause: str
    page_start: int
    page_end: int
    text: str                      # the clause text itself
    text_for_embedding: str = ""   # text + a context header (see below)
    char_count: int = 0
    pages: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def body_font_size(lines: list[Line]) -> float:
    """The most common font size in the document = normal paragraph text."""
    return Counter(l.size for l in lines).most_common(1)[0][0]


def heading_level(line: Line, body_size: float) -> int:
    """
    0 = normal text, 1 = big section heading, 2 = clause / sub-heading.
    Uses layout (font size, bold) first, then text patterns as a fallback.
    """
    text = line.text
    short = len(text) <= 90 and not text.endswith((".", ",", ";"))
    if not short or not HAS_WORD_RE.search(text):  # bullets like "•" are never headings
        return 0

    emphasised = line.bold or line.size >= body_size + 1
    if line.size >= body_size + 2 or (emphasised and SECTION_WORD_RE.match(text)):
        return 1
    if text.isupper() and len(text) > 4 and line.bold:
        return 1
    if CODE_RE.match(text):
        return 2
    if line.bold and (NUMBERED_RE.match(text) or len(text) <= 60):
        return 2
    if line.size >= body_size + 1:
        return 2
    return 0


def build_chunks(
    lines: list[Line],
    policy_name: str,
    max_chars: int = 1500,
    overlap_paragraphs: int = 1,
) -> list[Chunk]:
    body = body_font_size(lines)

    # 1) Walk through lines, grouping text under the current section/clause
    groups: list[dict] = []
    section, clause = "General", ""
    current = {"section": section, "clause": clause, "lines": []}

    for line in lines:
        level = heading_level(line, body)
        if level == 1:
            groups.append(current)
            section, clause = line.text.title() if line.text.isupper() else line.text, ""
            current = {"section": section, "clause": clause, "lines": []}
        elif level == 2:
            groups.append(current)
            clause = line.text
            current = {"section": section, "clause": clause, "lines": []}
        else:
            current["lines"].append(line)
    groups.append(current)
    groups = [g for g in groups if g["lines"]]  # drop empty headings

    # 2) Turn each group into one or more chunks
    chunks: list[Chunk] = []
    for g in groups:
        paragraphs = _merge_into_paragraphs(g["lines"])
        for part in _split_long(paragraphs, max_chars, overlap_paragraphs):
            text = "\n".join(p["text"] for p in part)
            pages = sorted({pg for p in part for pg in p["pages"]})
            chunk_id = f"{_slug(policy_name)}-{len(chunks):04d}"

            # Contextual header: the chunk "knows" where it came from.
            # "Not covered for 24 months" alone is useless; with the header
            # the embedding also knows it is about cataract under waiting periods.
            location = g["section"] + (f" > {g['clause']}" if g["clause"] else "")
            header = f"[Policy: {policy_name} | {location}]"

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    policy_name=policy_name,
                    section=g["section"],
                    clause=g["clause"],
                    page_start=pages[0],
                    page_end=pages[-1],
                    pages=pages,
                    text=text,
                    text_for_embedding=f"{header}\n{text}",
                    char_count=len(text),
                )
            )
    return chunks


def _merge_into_paragraphs(lines: list[Line]) -> list[dict]:
    """PDF lines are visual lines; join them back into paragraphs."""
    paragraphs: list[dict] = []
    buf, pages = [], set()
    for l in lines:
        buf.append(l.text)
        pages.add(l.page)
        # A line ending with sentence punctuation or a bullet start = paragraph break
        if l.text.endswith((".", ":", ";")) or re.match(r"^[•\-•(a-z]\)?\s", l.text):
            paragraphs.append({"text": " ".join(buf), "pages": set(pages)})
            buf, pages = [], set()
    if buf:
        paragraphs.append({"text": " ".join(buf), "pages": set(pages)})
    return paragraphs


def _split_long(paragraphs: list[dict], max_chars: int, overlap: int) -> list[list[dict]]:
    """Split a long section into windows of <= max_chars, repeating `overlap`
    paragraphs between windows so no rule is cut off from its context."""
    parts, current, size = [], [], 0
    for p in paragraphs:
        if current and size + len(p["text"]) > max_chars:
            parts.append(current)
            current = current[-overlap:] if overlap else []
            size = sum(len(x["text"]) for x in current)
        current.append(p)
        size += len(p["text"])
    if current:
        parts.append(current)
    return parts


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
