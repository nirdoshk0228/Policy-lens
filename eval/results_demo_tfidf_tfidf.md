# Retrieval evaluation (demo)

Embeddings: `tfidf:tfidf` · Questions: 32

| Setup | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|
| BM25 only | 81% | 84% | 84% | 0.83 |
| Vector only | 72% | 84% | 88% | 0.79 |
| Hybrid (RRF) | 81% | 84% | 84% | 0.83 |

## hit@3 by question type

| Setup | code (n=3) | cross-policy (n=2) | keyword (n=18) | paraphrase (n=9) |
|---|---|---|---|---|
| BM25 only | 100% | 100% | 100% | 44% |
| Vector only | 100% | 100% | 100% | 44% |
| Hybrid (RRF) | 100% | 100% | 100% | 44% |
