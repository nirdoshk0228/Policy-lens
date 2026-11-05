"""
PolicyLens agent = LLM (brain) + MCP tools (hands).

Flow for one question:
  1. Start the MCP server and connect as an MCP client.
  2. Ask the server which tools it has (names + JSON schemas) and hand them to the LLM.
  3. Loop: the LLM either asks for a tool call -> we run it through MCP and give
     the result back, or it writes the final answer.
  4. Return the answer plus a trace of every tool call (shown in the UI).

The agent never imports the search or calculator code directly; it only knows
the MCP server. Swap the LLM (OpenAI / Groq / Ollama) via config, the tools stay
the same. Point Claude Desktop at the same server and it gets the same tools.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import config

ROOT = Path(__file__).resolve().parents[1]
MAX_STEPS = 8

SYSTEM_PROMPT = """You are PolicyLens, an assistant that explains health insurance policy wordings in plain language.

Rules:
1. Use ONLY information returned by the tools. Do not use outside knowledge about insurance products.
2. Always call search_policy (or get_section / compare_policies) before answering a policy question.
   Use short focused queries; make several searches if the question has several parts.
3. Cite every policy fact like this: [Demo Health Shield, Section C > Code-Excl02, p.2] using the
   'cite' field from the tool result.
4. NEVER do arithmetic yourself. For any rupee amount (payable, deduction, out-of-pocket):
   a) first call search_policy for EACH rule that can change the amount: room rent / ICU limit,
      co-payment, waiting period for the treatment, and any sub-limit for the treatment
      (even if you saw some of them earlier in the conversation);
   b) then call calculate_claim with those rule values and the bill details from the user;
   c) explain the result using ONLY the 'steps' returned by calculate_claim, copied as they are.
      Do not write your own calculations or intermediate numbers.
   If a required number is missing, ask the user for it.
5. If the user did not name a policy: if only one policy is loaded, use it. If several are loaded,
   do NOT ask the user to choose — call compare_policies (or search each policy) and answer for every
   loaded policy, one short line each.
6. Waiting-period lists: apply a specific waiting period ONLY if the user's treatment or condition is
   named in the list (or is an obvious synonym, e.g. "kidney stones" = "calculi in urinary system").
   Never map a treatment onto a different listed condition (appendicitis is NOT hernia). If it is not
   listed, say so and apply only the general waiting periods (first 30 days, pre-existing disease).
7. If the clauses do not answer the question, say: "I could not find this in the policy wording."
8. Answer in short plain language first, then the citations. Mention that claim amounts are estimates."""


@dataclass
class AgentResult:
    answer: str
    trace: list[dict] = field(default_factory=list)  # every tool call: name, args, result


def make_llm_client():
    from openai import OpenAI
    if not config.LLM_API_KEY and "localhost" not in config.LLM_BASE_URL:
        raise RuntimeError("Set LLM_API_KEY (and LLM_BASE_URL / LLM_MODEL) in .env")
    # max_retries: the SDK waits and retries on 429 rate limits (common on free tiers)
    return OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY or "ollama",
                  max_retries=5, timeout=90)


def server_params() -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"],
                                 cwd=str(ROOT), env={**os.environ})


def mcp_tools_to_openai(tools) -> list[dict]:
    """MCP tool schema -> OpenAI function-calling schema (they are both JSON Schema)."""
    out = []
    for t in tools:
        schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None) or {"type": "object"}
        out.append({"type": "function",
                    "function": {"name": t.name, "description": t.description or "", "parameters": schema}})
    return out


def _tool_result_text(result) -> str:
    texts = [getattr(c, "text", "") for c in result.content]
    return "\n".join(t for t in texts if t) or "{}"


async def ask_async(question: str, history: list[dict] | None = None, llm=None,
                    model: str | None = None) -> AgentResult:
    llm = llm or make_llm_client()
    model = model or config.LLM_MODEL
    trace: list[dict] = []

    async with stdio_client(server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = mcp_tools_to_openai((await session.list_tools()).tools)

            messages = [{"role": "system", "content": SYSTEM_PROMPT}, *(history or []),
                        {"role": "user", "content": question}]

            for _ in range(MAX_STEPS):
                resp = llm.chat.completions.create(model=model, messages=messages, tools=tools,
                                                   tool_choice="auto", temperature=0)
                msg = resp.choices[0].message
                tool_calls = msg.tool_calls or []

                if not tool_calls:
                    return AgentResult(answer=msg.content or "", trace=trace)

                messages.append({
                    "role": "assistant", "content": msg.content or "",
                    "tool_calls": [{"id": tc.id, "type": "function",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                   for tc in tool_calls],
                })
                for tc in tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                        result_text = _tool_result_text(await session.call_tool(tc.function.name, args))
                    except Exception as e:  # bad JSON from the model or tool failure -> tell the model
                        args, result_text = {}, json.dumps({"error": f"{type(e).__name__}: {e}"})
                    trace.append({"tool": tc.function.name, "args": args, "result": _safe_json(result_text)})
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_text})

            return AgentResult(answer="Stopped after too many tool calls. Please rephrase the question.",
                               trace=trace)


def ask(question: str, history: list[dict] | None = None, llm=None, model: str | None = None) -> AgentResult:
    try:
        return asyncio.run(ask_async(question, history, llm, model))
    except BaseExceptionGroup as eg:  # anyio wraps errors from the MCP task group; show the real one
        raise root_cause(eg) from None


def root_cause(exc: BaseException) -> BaseException:
    """Unwrap nested ExceptionGroups down to the first real exception."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc


def _safe_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Is cataract surgery covered in Demo Health Shield, and after how long?"
    r = ask(q)
    for step in r.trace:
        print(f"-> {step['tool']}({json.dumps(step['args'])})")
    print("\n" + r.answer)
