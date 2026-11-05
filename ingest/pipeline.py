"""One function used by both the CLI and the Streamlit app."""

import json
from pathlib import Path

import config
from .extract import extract_lines
from .chunker import build_chunks


def ingest_pdf(pdf_path: str | Path, policy_name: str, max_chars: int = 1500,
               chunk_dir: Path = config.CHUNK_DIR) -> dict:
    lines = extract_lines(str(pdf_path))
    chunks = build_chunks(lines, policy_name=policy_name, max_chars=max_chars)
    chunk_dir = Path(chunk_dir)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    out = chunk_dir / f"{Path(pdf_path).stem}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
    return {"policy_name": policy_name, "lines": len(lines), "chunks": len(chunks), "path": str(out)}
