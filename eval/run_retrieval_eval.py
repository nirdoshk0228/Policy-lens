"""
Retrieval evaluation: does the right clause come back?

For each golden question we check whether a chunk from the expected clause
appears in the top-k results, for BM25 only, vector only, hybrid, and
hybrid + reranker (if a reranker is loaded).

Metrics
  hit@k : share of questions where a correct clause is in the top k
  MRR   : mean of 1/rank of the first correct clause (1.0 = always first)

    python -m eval.run_retrieval_eval              # your SBI policy (default)
    python -m eval.run_retrieval_eval --set demo   # the two fictional demo policies
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent


def is_correct(hit: dict, expected: list[list[str]]) -> bool:
    """expected = [[policy, fragment], ...]. A fragment matches the 'Section > Clause' label,
    or, if written as 'text:...', the chunk text (for chunks with no clause heading)."""
    label = (hit["section"] + " > " + hit["clause"]).lower()
    for pol, frag in expected:
        if hit["policy_name"] != pol:
            continue
        if frag.startswith("text:"):
            if frag[5:].lower() in hit["text"].lower():
                return True
        elif frag.lower() in label:
            return True
    return False


def evaluate(index, golden: list[dict], mode: str, rerank: bool, k: int = 5) -> dict:
    per_type = defaultdict(list)
    for g in golden:
        hits = index.search(g["question"], policy=g["policy"], k=k, mode=mode, rerank=rerank)
        rank = next((i + 1 for i, h in enumerate(hits) if is_correct(h, g["expected"])), None)
        per_type["all"].append(rank)
        per_type[g["type"]].append(rank)

    def summarise(ranks):
        n = len(ranks)
        return {
            "n": n,
            "hit@1": sum(r == 1 for r in ranks if r) / n,
            "hit@3": sum(r <= 3 for r in ranks if r) / n,
            "hit@5": sum(r is not None for r in ranks) / n,
            "mrr": sum(1 / r for r in ranks if r) / n,
        }

    return {t: summarise(r) for t, r in per_type.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="sbi", choices=["sbi", "demo"])
    ap.add_argument("--policy", default=None,
                    help="Name you gave the SBI policy when uploading (default: 'SBI Arogya Sanjeevani')")
    args = ap.parse_args()

    from eval.sets import choose
    golden_path = choose(args.set)          # must run before importing retrieval/config
    from retrieval import PolicyIndex

    golden = [json.loads(l) for l in golden_path.open(encoding="utf-8") if l.strip()]
    index = PolicyIndex()
    if args.policy:  # questions were written for one policy; point them at the name used on upload
        for g in golden:
            g["policy"] = args.policy
            g["expected"] = [[args.policy, frag] for _, frag in g["expected"]]

    needed = {g["policy"] for g in golden if g["policy"]}
    missing = needed - set(index.policies())
    if missing:
        raise SystemExit(f"Policy not loaded: {sorted(missing)}. Loaded: {index.policies()}\n"
                         f"Upload the PDF first (sidebar or scripts.run_ingest), or pass --policy \"<name you used>\".")

    configs = [("BM25 only", "bm25", False), ("Vector only", "vector", False), ("Hybrid (RRF)", "hybrid", False)]
    if index.reranker is not None:
        configs.append(("Hybrid + reranker", "hybrid", True))

    results = {name: evaluate(index, golden, mode, rr) for name, mode, rr in configs}

    lines = [f"# Retrieval evaluation ({args.set})\n",
             f"Embeddings: `{index.embedder.id}` · Questions: {len(golden)}\n",
             "| Setup | hit@1 | hit@3 | hit@5 | MRR |", "|---|---|---|---|---|"]
    for name, res in results.items():
        a = res["all"]
        lines.append(f"| {name} | {a['hit@1']:.0%} | {a['hit@3']:.0%} | {a['hit@5']:.0%} | {a['mrr']:.2f} |")

    types = sorted({g["type"] for g in golden})
    lines += ["\n## hit@3 by question type\n", "| Setup | " + " | ".join(f"{t} (n={sum(g['type']==t for g in golden)})" for t in types) + " |",
              "|---|" + "---|" * len(types)]
    for name, res in results.items():
        lines.append(f"| {name} | " + " | ".join(f"{res[t]['hit@3']:.0%}" for t in types) + " |")

    report = "\n".join(lines)
    print(report)
    out = HERE / f"results_{args.set}_{index.embedder.id.replace(':', '_').replace('/', '_')}.md"
    out.write_text(report + "\n")
    print(f"\nSaved -> {out}")


if __name__ == "__main__":
    main()
