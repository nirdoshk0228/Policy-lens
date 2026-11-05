"""
Tests the agent loop end to end WITHOUT a real LLM: a scripted fake model asks
for tools in order, and we check that the calls really go through the MCP
server and that results come back into the conversation.
"""

import json
from types import SimpleNamespace as NS

from agent import ask


class ScriptedLLM:
    def __init__(self, script):
        self.script = list(script)
        self.seen_messages = []
        self.seen_tools = None
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, model, messages, tools, **kw):
        self.seen_messages.append(list(messages))
        self.seen_tools = tools
        step = self.script.pop(0)
        if isinstance(step, str):
            msg = NS(content=step, tool_calls=None)
        else:
            calls = [NS(id=f"call_{i}", function=NS(name=n, arguments=json.dumps(a))) for i, (n, a) in enumerate(step)]
            msg = NS(content="", tool_calls=calls)
        return NS(choices=[NS(message=msg)])


def test_agent_calls_tools_through_mcp():
    llm = ScriptedLLM([
        [("search_policy", {"query": "knee replacement waiting period", "policy": "Demo Health Shield"}),
         ("search_policy", {"query": "room rent limit", "policy": "Demo Health Shield"})],
        [("calculate_claim", {"total_bill": 250000, "sum_insured": 500000, "days_admitted": 4,
                              "room_rent_per_day": 8000, "room_rent_limit_pct_of_si": 1, "copay_pct": 0,
                              "months_since_policy_start": 13, "waiting_period_months": 24})],
        "Not payable yet: knee replacement has a 24-month waiting period [Demo Health Shield, ...].",
    ])
    r = ask("Will my knee replacement be paid? Policy is 13 months old.", llm=llm, model="fake")

    assert [t["tool"] for t in r.trace] == ["search_policy", "search_policy", "calculate_claim"]
    assert any("Excl02" in h["clause"] for h in r.trace[0]["result"]["results"][:3])
    assert r.trace[2]["result"]["status"] == "rejected_waiting_period"
    assert r.answer.startswith("Not payable")
    # tool schemas discovered from MCP were offered to the LLM
    assert {t["function"]["name"] for t in llm.seen_tools} >= {"search_policy", "calculate_claim"}
    # tool results were fed back to the LLM before its final answer
    assert sum(m["role"] == "tool" for m in llm.seen_messages[-1]) == 3


def test_agent_survives_bad_tool_arguments():
    llm = ScriptedLLM([[("get_section", {"policy": "Unknown", "clause": "x"})], "I could not find this."])
    r = ask("?", llm=llm, model="fake")
    assert "error" in r.trace[0]["result"]
    assert r.answer == "I could not find this."


def test_llm_error_is_unwrapped():
    import pytest

    class Boom:
        chat = NS(completions=NS(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("429 rate limit reached"))))

    with pytest.raises(RuntimeError, match="429 rate limit"):
        ask("x", llm=Boom(), model="fake")
