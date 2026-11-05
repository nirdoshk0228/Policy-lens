"""
Step A.1 — Extract text from a policy PDF, line by line, with layout info.

Why not just page.get_text()?
Plain text loses formatting. We keep font size and bold for every line,
because that is how we later detect section headings ("EXCLUSIONS",
"4.2 Room Rent") without any hard-coded rules for a specific insurer.

We also remove running headers/footers (insurer name, UIN, "Page 3 of 40")
that repeat on every page — otherwise they pollute every chunk.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

import pymupdf

BOLD_FLAG = 16  # PyMuPDF span flag bit for bold text
# Some insurer PDFs embed fonts whose ligature glyphs (fi, fl, ff, ffi) come out
# as random Latin letters, e.g. "speciĤed", "ĥoater", "oĦce", "suģering".
# Seen in real policy wordings; without this fix BM25 never matches "floater".
BROKEN_LIGATURES = {"Ĥ": "fi", "ĥ": "fl", "Ħ": "ffi", "ģ": "ff", "ħ": "ffl"}
_LIG_RE = re.compile("|".join(BROKEN_LIGATURES))
RUPEE_BACKTICK_RE = re.compile(r"`\s?(?=\d)")


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)          # real ligatures: "ﬁ" -> "fi"
    text = _LIG_RE.sub(lambda m: BROKEN_LIGATURES[m.group()], text)
    text = RUPEE_BACKTICK_RE.sub("₹", text)  # Rupee-font PDFs encode ₹ as a backtick: "` 5,000"
    return re.sub(r"\s+", " ", text).strip()


LIGATURE_CHARS = set(BROKEN_LIGATURES) | set("ﬀﬁﬂﬃﬄ")


def _join_spans(parts: list[str]) -> str:
    """Join text spans with a space, except around a ligature glyph that sits in
    its own span ("speci" + "Ĥ" + "ed" must become "specified", not "speci fi ed")."""
    out = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        glued = out and (out[-1] in LIGATURE_CHARS or piece[0] in LIGATURE_CHARS) and not part[:1].isspace()
        out += piece if (glued or not out) else " " + piece
    return out


PAGE_NUM_RE = re.compile(r"^\s*(page\s*)?\d+\s*(of\s*\d+)?\s*$", re.IGNORECASE)


@dataclass
class Line:
    text: str
    page: int        # 1-based page number (used for citations)
    size: float      # font size of the line (rounded)
    bold: bool       # True if most of the line is bold
    y: float         # vertical position on the page (for header/footer detection)
    page_height: float


def extract_lines(pdf_path: str) -> list[Line]:
    """Read every text line in the PDF with its font size, boldness and page."""
    doc = pymupdf.open(pdf_path)
    lines: list[Line] = []

    for page_index, page in enumerate(doc):
        page_dict = page.get_text("dict")
        for block in page_dict["blocks"]:
            if block.get("type") != 0:  # 0 = text block, skip images
                continue
            for raw_line in block["lines"]:
                spans = [s for s in raw_line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = clean_text(_join_spans([s["text"] for s in spans]))

                # Size/bold of the line = whichever span covers the most characters
                total = sum(len(s["text"]) for s in spans)
                bold_chars = sum(len(s["text"]) for s in spans if s["flags"] & BOLD_FLAG)
                size = max(spans, key=lambda s: len(s["text"]))["size"]

                lines.append(
                    Line(
                        text=text,
                        page=page_index + 1,
                        size=round(size, 1),
                        bold=bold_chars / total > 0.6,
                        y=raw_line["bbox"][1],
                        page_height=page.rect.height,
                    )
                )
    doc.close()
    return remove_headers_footers(lines)


def remove_headers_footers(lines: list[Line], min_page_share: float = 0.5) -> list[Line]:
    """
    Drop text that sits in the top/bottom 8% of the page AND repeats on many
    pages (e.g. 'XYZ Health Insurance | UIN: ABC123'), plus bare page numbers.
    """
    n_pages = max((l.page for l in lines), default=1)

    def in_margin(l: Line) -> bool:
        return l.y < 0.08 * l.page_height or l.y > 0.92 * l.page_height

    # Normalise digits so "Page 3" and "Page 4" count as the same footer
    def key(l: Line) -> str:
        return re.sub(r"\d+", "#", l.text.lower())

    margin_counts = Counter(key(l) for l in lines if in_margin(l))
    # Must repeat on at least 2 pages — otherwise a real heading that just
    # happens to sit at the bottom of a page would be deleted as a "footer".
    min_count = max(2, min_page_share * n_pages)
    repeated = {k for k, c in margin_counts.items() if c >= min_count}

    cleaned = []
    for l in lines:
        if PAGE_NUM_RE.match(l.text):
            continue
        if in_margin(l) and key(l) in repeated:
            continue
        cleaned.append(l)
    return cleaned
