# Retrieval evaluation (sbi)

Embeddings: `tfidf:tfidf` · Questions: 23

| Setup | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|
| BM25 only | 65% | 83% | 83% | 0.72 |
| Vector only | 48% | 87% | 87% | 0.67 |
| Hybrid (RRF) | 65% | 87% | 87% | 0.75 |

## hit@3 by question type

| Setup | keyword (n=15) | paraphrase (n=8) |
|---|---|---|
| BM25 only | 100% | 50% |
| Vector only | 100% | 62% |
| Hybrid (RRF) | 100% | 62% |
