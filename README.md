# PolicyLens

Health insurance policy documents are 15–80 page PDFs that most people never read, so
they find out about room-rent limits, co-payments and waiting periods only when a claim
is cut. PolicyLens lets you upload a policy PDF and ask questions in plain English.
Every answer cites the clause and page it came from, and claim amounts are worked out
by a calculator rather than guessed by the LLM.

## Example (real SBI General Arogya Sanjeevani policy)

**Q:** Sum insured 5 lakh, 4 days in a ₹8,000/day room, bill ₹2.5 lakh including ₹50,000
medicines, policy 3 years old, appendix surgery. How much will I get?

**A:** ₹1,66,250 payable, ₹83,750 out of pocket.
- Room rent limit = lower of 2% of SI and ₹5,000 → ₹5,000/day (p.11)
- Room taken above the limit → other expenses paid in proportion 5,000/8,000 = 62.5% (p.4)
- Medicines exempt from the deduction (p.4)
- 5% co-payment on every claim (p.8)

**Q:** Same surgery, ₹1 lakh bill, ₹4,000/day room, policy 1 year old?
**A:** Covered, ₹95,000 payable. Appendicitis is not on the 24/36-month waiting lists, and
the room is within the limit, so only the 5% co-payment applies.

## Architecture

```
               upload PDF
                   │
   ┌───────────────▼────────────────┐
   │ Ingestion                       │  PyMuPDF → clean text → split by clause
   │                                 │  (headings found from font size / bold)
   └───────────────┬────────────────┘
                   │ chunks with policy, section, clause, page
   ┌───────────────▼────────────────┐
   │ Search index                    │  BM25 (exact words) + bge-small embeddings
   │                                 │  in ChromaDB → rank fusion → reranker
   └───────────────┬────────────────┘
                   │
   ┌───────────────▼────────────────┐        ┌─────────────────────────┐
   │ MCP server (5 tools)            │◄──────►│ Agent (Groq LLM)         │◄── question
   │  list_policies   search_policy  │  MCP   │ decides which tools to   │
   │  get_section     compare_policies│       │ call, writes the answer  │──► answer + citations
   │  calculate_claim (plain Python) │        └─────────────────────────┘
   └─────────────────────────────────┘          Streamlit UI / Claude Desktop
```

- **Ingestion** splits the policy at its own clause headings, so one exclusion is never
  cut in half, and keeps the page number of every piece for citations.
- **Search** combines keyword search (good for codes like `Code-Excl02`) with semantic
  search (good for "LASIK" → *Refractive Error*), then a cross-encoder reranks the top 20.
- **MCP server** exposes search and the claim calculator as tools. The same server works
  with my Streamlit agent and with Claude Desktop without code changes.
- **Claim calculator** applies room-rent caps, proportionate deduction, sub-limits,
  co-payment and waiting periods in fixed code, and returns every step.

## Results

Retrieval on a 32-question test set (2 sample policies), bge-small + bge-reranker:

| Setup | hit@1 | hit@3 | MRR | Exact codes (hit@3) | Paraphrased questions (hit@3) |
|---|---|---|---|---|---|
| Keyword only (BM25) | 81% | 84% | 0.83 | 100% | 44% |
| Semantic only | 91% | 97% | 0.95 | 67% | 100% |
| Hybrid (rank fusion) | 81% | 94% | 0.88 | 100% | 78% |
| **Hybrid + reranker** | **91%** | **97%** | **0.95** | **100%** | **89%** |

Keyword search misses reworded questions and semantic search misses exact codes; the
hybrid with a reranker is the only setup that does well on both.

On the real SBI policy, both claim questions above returned the correct amount, and the
16 automated tests (`pytest`) cover PDF cleaning, the calculator, the MCP server and the
agent loop.

Problems found while testing on the real PDF and fixed:
- broken "fi/fl/ff" characters in the PDF text ("speciĤed" → "specified")
- the agent skipped the co-payment once, so `copay_pct` is now a required tool input
- the agent once treated appendicitis as hernia, so waiting periods now apply only to
  treatments named in the list

## Run it

Needs Python 3.12 (Windows) and a free Groq API key.

```powershell
.\setup.ps1                     # creates .venv, installs packages, runs tests
notepad .env                    # paste your Groq key
.venv\Scripts\Activate.ps1
streamlit run app.py            # upload a policy PDF in the sidebar and ask
```

Other: `python -m eval.run_retrieval_eval --set demo` (retrieval metrics),
`pytest -q` (tests). To use the tools in Claude Desktop, see
`claude_desktop_config.example.json`.

## Limitations

- Scanned PDFs need OCR first; tables are read as plain text.
- Two-column layouts sometimes put a clause under the wrong section name.
- The claim amount is an estimate; it does not cover every non-payable item.

**Stack:** Python, PyMuPDF, ChromaDB, rank-bm25, sentence-transformers, MCP Python SDK,
OpenAI-compatible client (Groq), Streamlit, pytest.
