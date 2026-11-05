"""
PolicyLens — Streamlit UI.
    streamlit run app.py

Sidebar: upload a policy PDF -> ingested + indexed.
Main:    chat with the agent; every answer shows which MCP tools were called.
         "Search only" mode works without any LLM key (shows matching clauses).
"""

import json
import re
from pathlib import Path

CALC_TOOL = "calculate_claim"

import streamlit as st

import config
from ingest.pipeline import ingest_pdf
from retrieval import PolicyIndex
from tools.claim_calculator import _inr

st.set_page_config(page_title="PolicyLens", page_icon=":mag:", layout="wide")


@st.cache_resource(show_spinner="Loading search index...")
def get_index() -> PolicyIndex:
    return PolicyIndex()


index = get_index()


def add_policy(uploaded_file, policy_name: str) -> dict:
    """Save the uploaded PDF, chunk it and refresh the search index."""
    config.POLICY_DIR.mkdir(parents=True, exist_ok=True)
    target = config.POLICY_DIR / Path(uploaded_file.name).name
    target.write_bytes(uploaded_file.getvalue())
    with st.spinner(f"Reading and indexing {uploaded_file.name}..."):
        info = ingest_pdf(target, policy_name)
        index.refresh()
    return info


def show_trace(trace: list[dict]) -> None:
    """Show the calculator's own steps (ground truth), then every raw tool call."""
    for step in trace:
        res = step["result"]
        if step["tool"] == CALC_TOOL and isinstance(res, dict) and "steps" in res:
            lines = "\n".join(f"- {s}" for s in res["steps"])
            st.info(f"**Calculator result: ₹{_inr(res['estimated_payable'])} payable, "
                    f"₹{_inr(res['out_of_pocket'])} out of pocket**\n\n{lines}")
    with st.expander(f"Tool calls ({len(trace)})"):
        for step in trace:
            st.markdown(f"**{step['tool']}** `{json.dumps(step['args'])}`")
            st.json(step["result"], expanded=False)


def remove_policy(policy_name: str) -> None:
    """Delete the chunk file(s) of one policy and rebuild the index."""
    for f in config.CHUNK_DIR.glob("*.jsonl"):
        first = f.open(encoding="utf-8").readline()
        if first and json.loads(first)["policy_name"] == policy_name:
            f.unlink()
    index.refresh()

# ---------------- Sidebar: policies ----------------
with st.sidebar:
    st.header("Policies")
    uploaded = st.file_uploader("Upload policy wording (PDF)", type="pdf")
    default_name = ""
    if uploaded:  # pre-fill a readable name from the file name, user can edit it
        default_name = re.sub(r"[_\-]+", " ", Path(uploaded.name).stem).strip().title()
    name = st.text_input("Policy name (used in citations)", value=default_name,
                         key=f"name_{uploaded.name if uploaded else ''}")
    if uploaded and name.strip() not in index.policies():
        st.info("Click **Add policy** to load this PDF.")
    if st.button("Add policy", type="primary", disabled=not (uploaded and name.strip())):
        info = add_policy(uploaded, name.strip())
        st.success(f"Added {info['policy_name']}: {info['chunks']} clauses")

    loaded = index.policies()
    st.caption(f"{len(loaded)} loaded")
    for p in loaded:
        with st.expander(p):
            if st.button("Remove this policy", key=f"rm_{p}"):
                remove_policy(p)
                st.rerun()
            st.write("\n".join(f"- {c}" for c in index.clauses(p)))

    st.divider()
    mode = st.radio("Mode", ["Agent (LLM + MCP tools)", "Search only (no LLM)"],
                    help="Search only shows the retrieved clauses; useful without an API key.")
    st.caption(f"LLM: `{config.LLM_MODEL}` · Embeddings: `{index.embedder.id}` · "
               f"Reranker: `{'on' if index.reranker else 'off'}`")

# ---------------- Main: chat ----------------
st.title("PolicyLens")
st.caption("Ask about your health insurance policy. Answers cite the clause and page.")
if not loaded:
    st.info("No policy loaded yet. Upload a policy wording PDF in the sidebar and click **Add policy**.")

if "messages" not in st.session_state:
    st.session_state.messages = []  # {"role", "content", "trace"}

examples = ["What is the room rent limit?",
            "Is cataract surgery covered, and after how long?",
            "SI 5 lakh, 4 days in an Rs 8,000/day room, bill Rs 2.5 lakh including Rs 50,000 medicines. "
            "Policy is 3 years old, it was an appendix surgery. How much will I get?"]
cols = st.columns(len(examples))
clicked = None
for col, ex in zip(cols, examples):
    if col.button(ex[:60] + ("..." if len(ex) > 60 else ""), use_container_width=True):
        clicked = ex

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("trace"):
            show_trace(m["trace"])

question = (st.chat_input("Ask a question about the policy") or clicked
            or st.session_state.pop("pending_question", None))
if question and uploaded and name.strip() and name.strip() not in index.policies():
    # The user picked a PDF but asked before clicking "Add policy": add it for them,
    # then rerun so the sidebar shows it, and answer the same question.
    add_policy(uploaded, name.strip())
    st.session_state.pending_question = question
    st.rerun()
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        if not loaded:
            answer, trace = "Please upload a policy PDF first.", []
        elif mode.startswith("Search"):
            hits = index.search(question, k=5)
            answer = "\n\n".join(f"**{h['cite']}**\n\n> {h['text'][:600]}" for h in hits) or "No match."
            trace = []
        else:
            from agent import ask
            history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[:-1]][-6:]
            with st.spinner("Thinking and calling tools..."):
                try:
                    r = ask(question, history=history)
                    answer, trace = r.answer, r.trace
                except Exception as e:
                    msg = str(e)
                    hint = ""
                    if "rate" in msg.lower() or "429" in msg or "413" in msg or "too large" in msg.lower():
                        hint = "\n\nThe free LLM tier hit its per-minute limit. Wait a minute and ask again."
                    elif "401" in msg or "api key" in msg.lower():
                        hint = "\n\nCheck LLM_API_KEY in your .env file."
                    answer, trace = f"Agent error ({type(e).__name__}): {msg}{hint}", []
        st.markdown(answer)
        if trace:
            show_trace(trace)
    st.session_state.messages.append({"role": "assistant", "content": answer, "trace": trace})
