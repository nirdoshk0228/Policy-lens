# Retrieval evaluation (demo)

Embeddings: `st:BAAI/bge-small-en-v1.5` · Reranker: `BAAI/bge-reranker-base` · Questions: 32
(Run on Windows laptop, 2 Nov 2026.)

| Setup | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|
| BM25 only | 81% | 84% | 84% | 0.83 |
| Vector only | 91% | 97% | 100% | 0.95 |
| Hybrid (RRF) | 81% | 94% | 97% | 0.88 |
| Hybrid + reranker | 91% | 97% | 100% | 0.95 |

## hit@3 by question type

| Setup | code (n=3) | cross-policy (n=2) | keyword (n=18) | paraphrase (n=9) |
|---|---|---|---|---|
| BM25 only | 100% | 100% | 100% | 44% |
| Vector only | 67% | 100% | 100% | 100% |
| Hybrid (RRF) | 100% | 100% | 100% | 78% |
| Hybrid + reranker | 100% | 100% | 100% | 89% |
