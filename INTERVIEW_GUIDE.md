# PolicyLens — Interview Guide

## 30-second pitch

"Health insurance policies are 40–80 page PDFs that almost nobody reads, so people
find out about waiting periods and room-rent limits only at claim time. I built
PolicyLens: a RAG pipeline with clause-level chunking and hybrid search that answers
policy questions with clause and page citations. For complex claim questions, an
agent calls tools on an MCP server that I wrote, and all amounts are calculated
in deterministic Python instead of by the LLM. I measured retrieval with a 32-question
test set comparing BM25, vector and hybrid search."

## The flow in one breath

PDF → text with font sizes → headers/footers removed → clauses detected from bold or
bigger fonts → each clause is a chunk with policy/section/page metadata → embedded
with bge-small into Chroma + a BM25 index → question → both searches → RRF merge →
reranker → top 5 clauses → LLM answers only from them, with citations.

## Likely questions and answers

**Q: What is RAG and why not just give the whole PDF to the LLM?**
RAG means first finding the relevant pieces, then giving only those to the LLM. A
full policy is long and costs a lot of tokens, and the LLM gets confused by irrelevant
text. RAG also gives exact citations. With several policies loaded, the full text
won't even fit.

**Q: How did you chunk?**
By clause, using headings detected from font size and bold, not fixed 500-token
windows. A fixed window can cut an exclusion in half. Long sections are split with
one paragraph of overlap. Each chunk gets a header like `[Policy | Section > Clause]`
so the embedding knows the context.

**Q: Why hybrid search?**
Vector search understands meaning ("eye lens surgery" ≈ cataract) but is weak on
exact codes like `Code-Excl02`. BM25 is the opposite. RRF merges the two ranked
lists using only ranks: score = Σ 1/(60 + rank), so no score normalisation is needed.

**Q: What does the reranker do?**
Embeddings encode the question and the chunk separately (bi-encoder): fast but
approximate. A cross-encoder reads both together and scores the pair: slower but
more accurate. So I retrieve 20 cheaply and rerank only those 20.

**Q: What is MCP and why did you use it?**
Model Context Protocol is a standard way for an AI app to discover and call tools.
My server exposes 5 tools with JSON schemas. My Streamlit agent connects to it as
an MCP client, and Claude Desktop can connect to the same server without code
changes. It decouples the "brain" (LLM) from the "hands" (tools). I can swap OpenAI
for Llama and the tools don't change. The LLM also gets only these 5 actions, not
raw database access.

**Q: MCP vs normal function calling?**
Function calling is how an LLM *asks* for a tool. MCP is how tools are *served*:
discovery, schemas, transport (stdio/HTTP), reusable across clients. My agent uses
both: it reads tools from MCP and passes them to the LLM as function definitions.

**Q: How do you stop hallucination?**
(1) The system prompt allows answers only from tool results. (2) Every fact needs
a citation from the tool's `cite` field. (3) The model must say "not found" if the
clauses don't answer. (4) All maths goes to `calculate_claim`. (5) The eval checks
the citation rate.

**Q: How did you evaluate?**
32 golden questions with the known correct clause, tagged keyword / code /
paraphrase / cross-policy. Metrics: hit@1, hit@3, hit@5, MRR for each search setup.
Finding: word-based search got 100% on keyword questions but only 44% on paraphrased
ones, which is the reason for semantic embeddings + hybrid search. Answer eval checks
that the key facts and a citation appear in the agent's answer.

**Q: What would you improve / how to scale?**
Table-aware extraction, OCR for scanned PDFs, metadata filters (only exclusions),
caching embeddings, HTTP transport for the MCP server so many users share it, auth
on the server, observability (log every tool call and latency), and LLM-as-judge
for answer evaluation.

**Q: A bug you hit?**
Real PDFs were the hardest part. In the SBI Arogya Sanjeevani wording, the "fi/fl/ff"
ligatures came out as junk characters ("speciĤed", "ĥoater"), so keyword search could
never match "floater". I mapped those glyphs back and glued text spans around them.
Body sentences starting with "Schedule..." were wrongly detected as section headings,
and every bullet became a clause. I tightened heading detection and added unit tests
for each case. Smaller ones: a heading at a page bottom was deleted as a "footer"
(fixed by requiring repetition on ≥2 pages), and the `mcp` SDK moved to v2
(FastMCP → MCPServer), so the server supports both.

**Q: Did the agent ever give a wrong answer? What did you do?**
Yes. For "SI 5 lakh, ₹8,000 room, ₹2.5 lakh bill" it said ₹1,75,000; correct is ₹1,66,250.
Two failures: (1) it called the calculator straight away, using room-rent numbers remembered
from earlier in the chat, and never searched for the 5% co-payment; (2) it wrote its own
"working" next to the tool's number, and that working was wrong (its own steps added up
to ₹1,95,000). Fixes at three levels: made `copay_pct` a *required* parameter in the MCP
tool schema so the model cannot skip it; changed the prompt to search every rule (room
rent, co-pay, waiting period, sub-limit) before calculating and to explain only with the
tool's returned steps; and the UI now renders the calculator's own steps in a separate
box, so the user always sees the deterministic numbers. Lesson: don't rely on the prompt
alone, put guardrails in the tool schema and in the UI.

**Q: How did the LLM know "2% of SI, max ₹5,000"?**
It doesn't calculate. It passes both numbers from the clause to `calculate_claim`
(`room_rent_limit_pct_of_si=2`, `room_rent_limit_per_day=5000`) and the tool applies
the lower one, and shows each step. Same for the cataract sub-limit (25% of SI or ₹40,000).

## Numbers to remember

- Real policy: SBI General Arogya Sanjeevani, 14 pages → 113 clause chunks
- Demo eval (32 questions, bge-small + reranker):
  hit@1 **91%**, MRR **0.95**, exact-code hit@3 **100%**
- Paraphrase hit@3: BM25 **44%** → hybrid + reranker **89%**
- Plain RRF dropped hit@1 to 81% → reranker brought it back to 91%
- SBI eval (23 questions): TF-IDF baseline hybrid hit@3 87%; bge number: __
- Answer eval: fact accuracy __% · citation rate __%
- LLM: openai/gpt-oss-120b on Groq · 5 MCP tools · 16 tests
