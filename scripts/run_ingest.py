"""
Usage:
    python -m scripts.run_ingest data/policies/my_policy.pdf --name "Star Comprehensive"

Writes data/chunks/<file>.jsonl and prints a summary so you can check
that sections were detected correctly.
"""

import argparse
import json
from collections import Counter

from ingest.pipeline import ingest_pdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--name", required=True, help="Policy name used in citations")
    ap.add_argument("--max-chars", type=int, default=1500)
    args = ap.parse_args()

    info = ingest_pdf(args.pdf, args.name, max_chars=args.max_chars)
    chunks = [json.loads(l) for l in open(info["path"], encoding="utf-8")]
    sizes = [c["char_count"] for c in chunks]
    print(f"Lines extracted : {info['lines']}")
    print(f"Chunks created  : {info['chunks']}")
    print(f"Chunk size chars: min {min(sizes)}, avg {sum(sizes)//len(sizes)}, max {max(sizes)}")
    print("\nChunks per section:")
    for sec, n in Counter(c["section"] for c in chunks).items():
        print(f"  {n:3d}  {sec}")
    print(f"\nSaved -> {info['path']}")


if __name__ == "__main__":
    main()
