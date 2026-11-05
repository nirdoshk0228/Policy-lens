# PolicyLens

Ask plain-language questions about health insurance policy wordings and get answers
with clause and page citations. Complex claim questions are handled by an agent that
calls tools on an **MCP server** (hybrid RAG search + a deterministic claim calculator).

```
                ┌──────────────────────── MCP (JSON-RPC over stdio) ───────────────────────┐
 Streamlit UI ─►│ Agent (any OpenAI-compatible LLM)        PolicyLens MCP server            │
 Claude Desktop►│   discovers tools ─────────────────────►  list_policies                   │
                │   decides which to call                   search_policy  ─► BM25 + Chroma │
                │   writes cited answer  ◄── JSON results   get_section       ─► RRF ─► rerank│
                │                                           compare_policies                │
                │                                           calculate_claim ─► pure Python  │
                └───────────────────────────────────────────────────────────────────────────┘
 Ingestion:  PDF ─► lines + font info ─► strip headers/footers ─► section/clause chunks ─► embeddings
```

## Quick start (Windows)

```powershell
cd $HOME\Downloads\policylens
.\setup.ps1                      # Python 3.12 venv + packages + tests (one time)
notepad .env                     # paste your Groq key (console.groq.com -> API Keys)
.venv\Scripts\Activate.ps1
streamlit run app.py             # UI: upload a policy PDF in the sidebar, then ask
```

Other commands (with the venv active):

```powershell
python -m agent.agent "What is the room rent limit?"          # CLI agent
python -m scripts.run_ingest data\policies\new.pdf --name "My Policy"   # add a policy
python -m eval.run_retrieval_eval --policy "SBI Arogya Sanjeevani"   # after uploading the SBI PDF
python -m eval.run_retrieval_eval --set demo   # retrieval metrics on the 2 demo policies
python -m eval.run_answer_eval --policy "SBI Arogya Sanjeevani" --limit 5   # answer metrics (calls the LLM)
pytest -q                                      # 16 offline tests
```

Policies can also be added and removed from the Streamlit sidebar.

### Use the same tools from Claude Desktop

Copy `claude_desktop_config.example.json` into Claude Desktop's config file, fix the
two absolute paths, restart Claude Desktop. The `policylens` tools appear in Claude
without any change to the server code.

## Project layout

```
ingest/         extract.py (PDF → lines), chunker.py (clause chunks), pipeline.py
retrieval/      embedder.py (bge or TF-IDF), index.py (Chroma + BM25 + RRF + reranker)
tools/          claim_calculator.py (deterministic, audited steps)
mcp_server/     server.py — the 5 MCP tools
agent/          agent.py — MCP client + LLM tool-calling loop
app.py          Streamlit UI (agent mode + search-only mode)
eval/           golden.jsonl, run_retrieval_eval.py, run_answer_eval.py
tests/          calculator, extraction, MCP server over stdio, agent loop with a fake LLM
tests/fixtures/ the 2 fictional demo policies (tests run on a temp copy of these)
data/           policies users upload: policies/*.pdf, chunks/*.jsonl, index/ (starts empty)
```

## Design decisions

| Area | Decision | Why |
|---|---|---|
| Chunking | Split at headings detected from font size/bold; 1-paragraph overlap for long sections | Clauses are the natural unit; fixed windows cut exclusions in half |
| Chunking | Context header `[Policy \| Section > Clause]` prepended before embedding | "Excluded for 24 months" alone is ambiguous |
| Ingestion | Drop lines repeating in page margins on ≥2 pages | Removes insurer name / UIN / page numbers without deleting real headings |
| Retrieval | BM25 + vector, merged with Reciprocal Rank Fusion | Vectors handle synonyms; BM25 handles exact codes like `Code-Excl02` |
| Retrieval | Cross-encoder reranker on top-20 | More accurate pair scoring, affordable on a small candidate set |
| Vector DB | Chroma, rebuilt only when chunks or embedding model change (fingerprint) | Fast restarts, no stale vectors |
| Answers | System prompt: answer only from tool results, cite every fact, say "not found" | Grounding, reduces hallucination |
| Maths | `calculate_claim` tool, LLM never computes amounts | LLMs are unreliable at arithmetic; every step is auditable |
| MCP | Tools live in a separate MCP server; the agent is just an MCP client | Same tools for our agent and Claude Desktop; LLM provider can be swapped |
| LLM | OpenAI-compatible client | Works with OpenAI, Groq, OpenRouter, local Ollama |

## Evaluation

Two golden sets:
- `eval/golden_sbi.jsonl` — 23 questions on the real SBI General Arogya Sanjeevani wording
  (upload that PDF first; `--policy` = the name you gave it)
  (15 keyword, 8 paraphrase such as "LASIK for -3 glasses" → *Refractive Error*).
- `eval/golden_demo.jsonl` — 32 questions on the 2 fictional demo policies
  (keyword, exact `Code-ExclNN`, paraphrase, cross-policy).

**Demo set, bge-small + bge-reranker** (`eval/results_demo_st_BAAI_bge-small-en-v1.5.md`):

| Setup | hit@1 | hit@3 | hit@5 | MRR | hit@3 codes | hit@3 paraphrase |
|---|---|---|---|---|---|---|
| BM25 only | 81% | 84% | 84% | 0.83 | 100% | 44% |
| Vector only | 91% | 97% | 100% | 0.95 | 67% | 100% |
| Hybrid (RRF) | 81% | 94% | 97% | 0.88 | 100% | 78% |
| Hybrid + reranker | **91%** | **97%** | **100%** | **0.95** | **100%** | 89% |

BM25 misses paraphrases, vectors miss exact codes, plain RRF lets BM25 noise pull
hit@1 down, and the cross-encoder reranker recovers it while keeping exact codes at 100%.

**SBI set, offline TF-IDF baseline** (`eval/results_sbi_tfidf_tfidf.md`): hybrid hit@3
87%, keyword 100%, paraphrase 62%. Run `python -m eval.run_retrieval_eval` with the
default bge settings to get the semantic numbers.

## Real-PDF problems found and fixed

| Problem in the SBI PDF | Fix |
|---|---|
| Ligatures came out as junk: "speciĤed", "ĥoater", "oĦce" | Map broken glyphs back to fi/fl/ffi/ff + Unicode NFKC |
| Ligature glyph in its own text span → "speci fied" | Glue spans around ligature glyphs instead of joining with a space |
| Body lines starting with "Schedule…" / "Section 56()…" became sections | Section keywords count only for bold/large lines followed by a number/letter |
| Every bullet "•" became a clause heading | Lines without a real word are never headings |
| Rules like "2% of SI, max ₹5,000/day" and "25% of SI or ₹40,000, whichever is lower" | Calculator takes both values and applies the lower one |

## Known limitations

- Tables are read as plain lines; scanned PDFs need OCR first.
- Heading detection is layout-based; very unusual PDF layouts may need tuning.
- Claim estimate covers waiting period, room-rent proportionate deduction, treatment
  sub-limit, co-pay and sum-insured cap — not deductibles or non-payable items lists.
- Two-column layouts can attach a clause to the wrong *section* label (clause labels stay correct).
- Demo policies in `tests/fixtures` are fictional and exist only for testing.
