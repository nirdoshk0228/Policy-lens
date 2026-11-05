"""
PolicyLens MCP server.

Exposes the retrieval index and the claim calculator as MCP tools.
Any MCP client (our agent, Claude Desktop, Cursor ...) can:
  1. list the tools  -> gets names, descriptions and JSON input schemas
  2. call a tool     -> gets JSON back

Run standalone:   python -m mcp_server.server        (stdio transport)
The docstrings below ARE the tool descriptions the LLM reads, so they are
written as instructions to the model.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow running from anywhere

try:  # mcp SDK 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp SDK 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from retrieval import PolicyIndex
from tools import calculate_claim as _calculate_claim

mcp = _Server(
    "policylens",
    instructions="Tools to search health insurance policy wordings and estimate claims. "
                 "Answer only from returned clause texts and always cite them.",
)
_index: PolicyIndex | None = None


def index() -> PolicyIndex:
    global _index
    if _index is None:
        _index = PolicyIndex()
    else:
        _index.refresh()  # picks up newly uploaded policies; cheap if nothing changed
    return _index


def _brief(hit: dict, max_chars: int = 700) -> dict:
    return {
        "cite": hit["cite"],
        "policy": hit["policy_name"],
        "section": hit["section"],
        "clause": hit["clause"],
        "pages": hit["pages"],
        "text": hit["text"][:max_chars],
    }


@mcp.tool()
def list_policies() -> dict:
    """List the insurance policies currently loaded, with their sections and clauses.
    Call this first if the user has not said which policy they mean."""
    idx = index()
    return {"policies": [{"name": p, "clauses": idx.clauses(p)} for p in idx.policies()]}


@mcp.tool()
def search_policy(query: str, policy: str | None = None, k: int = 3) -> dict:
    """Search policy wordings for clauses relevant to a question (hybrid keyword + semantic search).
    Use short, specific queries, e.g. 'cataract waiting period' or 'room rent limit'.
    Optionally restrict to one policy by its exact name from list_policies.
    Returns the top 3 clause texts (shortened) with citations; answer ONLY from these texts.
    Use get_section if you need a clause in full."""
    idx = index()
    try:
        hits = idx.search(query, policy=policy, k=max(1, min(k, 6)))
    except ValueError as e:
        return {"error": str(e)}
    return {"query": query, "results": [_brief(h) for h in hits]}


@mcp.tool()
def get_section(policy: str, clause: str) -> dict:
    """Get the full text of a specific section or clause of a policy, e.g. clause='Room Rent'
    or clause='Code-Excl02'. Use after search_policy when you need the complete clause."""
    idx = index()
    if policy not in idx.policies():
        return {"error": f"Unknown policy '{policy}'. Loaded: {idx.policies()}"}
    labels = idx.clauses(policy)
    lowered = clause.lower()
    match = next((l for l in labels if lowered in l.lower()), None)
    if match is None:
        close = difflib.get_close_matches(clause, labels, n=1, cutoff=0.3)
        match = close[0] if close else None
    if match is None:
        return {"error": f"No clause like '{clause}'.", "available": labels}
    parts = [c for c in idx.chunks if c["policy_name"] == policy
             and (c["section"] + (f" > {c['clause']}" if c["clause"] else "")) == match]
    from retrieval import cite
    return {"cite": cite(parts[0]), "clause": match, "text": "\n".join(p["text"] for p in parts)}


@mcp.tool()
def compare_policies(topic: str, policies: list[str] | None = None) -> dict:
    """Compare how several policies handle one topic (e.g. 'co-payment', 'knee replacement waiting period').
    Returns the top clauses for the topic from each policy side by side."""
    idx = index()
    names = policies or idx.policies()
    out = {}
    for name in names:
        try:
            out[name] = [_brief(h, 500) for h in idx.search(topic, policy=name, k=2)]
        except ValueError as e:
            out[name] = {"error": str(e)}
    return {"topic": topic, "by_policy": out}


@mcp.tool()
def calculate_claim(
    total_bill: float,
    sum_insured: float,
    days_admitted: int,
    room_rent_per_day: float,
    copay_pct: float,
    room_rent_limit_per_day: float | None = None,
    room_rent_limit_pct_of_si: float | None = None,
    non_proportionate_amount: float = 0.0,
    sub_limit_pct_of_si: float | None = None,
    sub_limit_amount: float | None = None,
    already_claimed_this_year: float = 0.0,
    months_since_policy_start: float | None = None,
    waiting_period_months: float | None = None,
    is_accident: bool = False,
) -> dict:
    """Estimate the payable claim amount. ALWAYS use this instead of doing arithmetic yourself.
    BEFORE calling, search the policy for: room rent limit, co-payment, waiting period for this
    treatment, and any sub-limit for it. copay_pct is REQUIRED: pass the policy's co-pay %
    (pass 0 only if you searched and the policy has no co-payment).
    Take the rule values (room rent limit as % of sum insured or Rs/day, co-pay %, waiting period in months)
    from the policy clauses you retrieved, and the bill details from the user.
    Room rent limit like '2% of SI, max Rs 5,000/day': pass room_rent_limit_pct_of_si=2 AND
    room_rent_limit_per_day=5000; the lower one is used.
    non_proportionate_amount = items the policy exempts from proportionate deduction (e.g. medicines).
    Treatment sub-limit like cataract '25% of SI or Rs 40,000, whichever is lower':
    pass sub_limit_pct_of_si=25 and sub_limit_amount=40000; the lower one is used.
    Returns the payable amount and each calculation step."""
    try:
        return _calculate_claim(
            total_bill=total_bill, sum_insured=sum_insured, days_admitted=days_admitted,
            room_rent_per_day=room_rent_per_day, room_rent_limit_per_day=room_rent_limit_per_day,
            room_rent_limit_pct_of_si=room_rent_limit_pct_of_si,
            non_proportionate_amount=non_proportionate_amount,
            sub_limit_pct_of_si=sub_limit_pct_of_si, sub_limit_amount=sub_limit_amount,
            copay_pct=copay_pct,
            already_claimed_this_year=already_claimed_this_year,
            months_since_policy_start=months_since_policy_start,
            waiting_period_months=waiting_period_months, is_accident=is_accident,
        )
    except ValueError as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()  # stdio transport
