"""Starts the real MCP server as a subprocess and talks to it over stdio,
exactly like Claude Desktop or our agent would."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def _params():
    return StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"],
                                 cwd=str(ROOT), env={**os.environ})


async def _run():
    async with stdio_client(_params()) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name: t for t in (await s.list_tools()).tools}

            async def call(name, args):
                res = await s.call_tool(name, args)
                return json.loads(res.content[0].text)

            out = {
                "tools": tools,
                "policies": await call("list_policies", {}),
                "search": await call("search_policy", {"query": "cataract waiting period", "policy": "Demo Health Shield"}),
                "section": await call("get_section", {"policy": "Demo Care Plus", "clause": "co-payment"}),
                "compare": await call("compare_policies", {"topic": "co-payment"}),
                "claim": await call("calculate_claim", {"total_bill": 250000, "sum_insured": 500000, "days_admitted": 4,
                                                         "room_rent_per_day": 8000, "room_rent_limit_pct_of_si": 1, "copay_pct": 0,
                                                         "non_proportionate_amount": 50000}),
                "bad_policy": await call("search_policy", {"query": "x", "policy": "Nope"}),
            }
            return out


def test_mcp_end_to_end():
    out = asyncio.run(_run())
    assert set(out["tools"]) == {"list_policies", "search_policy", "get_section", "compare_policies", "calculate_claim"}
    t = out["tools"]["calculate_claim"]
    schema = getattr(t, "input_schema", None) or t.inputSchema  # mcp 2.x / 1.x
    assert "total_bill" in schema["properties"]
    assert {p["name"] for p in out["policies"]["policies"]} >= {"Demo Health Shield", "Demo Care Plus"}  # real policies may be added
    assert any("Excl02" in r["clause"] for r in out["search"]["results"][:3])
    assert "10%" in out["section"]["text"]
    assert set(out["compare"]["by_policy"]) >= {"Demo Health Shield", "Demo Care Plus"}
    assert out["claim"]["status"] == "payable" and out["claim"]["estimated_payable"] > 0
    assert "error" in out["bad_policy"]


def test_copay_is_required_in_schema():
    async def _schema():
        async with stdio_client(_params()) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                t = {t.name: t for t in (await s.list_tools()).tools}["calculate_claim"]
                return getattr(t, "input_schema", None) or t.inputSchema
    schema = asyncio.run(_schema())
    assert "copay_pct" in schema["required"]
