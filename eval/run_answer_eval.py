"""
Answer evaluation (needs an LLM key in .env).

Runs the full agent on every golden question and checks:
  - fact accuracy : every 'must_include' fact appears in the answer
  - citation rate : the answer contains at least one [Policy, Section ...] citation
  - tool use      : the agent called a retrieval tool before answering

    python -m eval.run_answer_eval                # your SBI policy, all questions
    python -m eval.run_answer_eval --limit 5      # quick check (free tiers have rate limits)
    python -m eval.run_answer_eval --set demo     # the fictional demo policies
"""

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
# Models cite with [..] or 【..】 brackets
CITE_RE = re.compile(r"[\[【]([^\]】]+,\s*[^\]】]*>[^\]】]*)[\]】]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--set", default="sbi", choices=["sbi", "demo"])
    ap.add_argument("--policy", default=None,
                    help="Name you gave the SBI policy when uploading (default: 'SBI Arogya Sanjeevani')")
    args = ap.parse_args()

    from eval.sets import choose
    golden_path = choose(args.set)          # must run before importing the agent/config
    from agent import ask

    golden = [json.loads(l) for l in golden_path.open(encoding="utf-8") if l.strip()][: args.limit]
    if args.policy:  # questions were written for one policy; point them at the name used on upload
        for g in golden:
            g["policy"] = args.policy
            g["expected"] = [[args.policy, frag] for _, frag in g["expected"]]

    rows, facts_ok, cited, used_tools = [], 0, 0, 0

    for g in golden:
        q = g["question"] if not g["policy"] else f"{g['question']} (policy: {g['policy']})"
        r = ask(q)
        ans = r.answer.lower()
        # each fact may list alternatives: "40,000|40000"
        ok = all(any(alt.lower() in ans for alt in f.split("|")) for f in g["must_include"])
        has_cite = bool(CITE_RE.search(r.answer))
        tool = any(t["tool"] in ("search_policy", "get_section", "compare_policies") for t in r.trace)
        facts_ok += ok; cited += has_cite; used_tools += tool
        rows.append({"id": g["id"], "facts_ok": ok, "cited": has_cite, "used_retrieval": tool,
                     "tools": [t["tool"] for t in r.trace], "answer": r.answer})
        print(f"{g['id']}  facts={'Y' if ok else 'N'}  cite={'Y' if has_cite else 'N'}  tools={[t['tool'] for t in r.trace]}")

    n = len(golden)
    summary = {"n": n, "fact_accuracy": facts_ok / n, "citation_rate": cited / n, "retrieval_tool_rate": used_tools / n}
    print(json.dumps(summary, indent=2))
    (HERE / f"answer_eval_{args.set}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
