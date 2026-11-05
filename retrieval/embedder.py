"""
Turns text into vectors.

Two backends behind one interface, so the rest of the code never changes:
  - "st":    sentence-transformers model (default BAAI/bge-small-en-v1.5).
             Captures meaning: "eye lens surgery" ~ "cataract".
  - "tfidf": word-weight vectors, no download needed. Only for offline tests;
             it matches words, not meaning.
"""

from __future__ import annotations

import numpy as np

# bge models were trained with this instruction in front of search queries
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    def __init__(self, backend: str = "st", model_name: str = "BAAI/bge-small-en-v1.5"):
        self.backend = backend
        self.model_name = model_name
        self._model = None
        self._vectorizer = None

        if backend == "st":
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
        elif backend != "tfidf":
            raise ValueError(f"Unknown embedding backend: {backend}")

    @property
    def id(self) -> str:
        return f"{self.backend}:{self.model_name if self.backend == 'st' else 'tfidf'}"

    def fit(self, corpus: list[str]) -> None:
        """Only TF-IDF needs to learn a vocabulary from the corpus."""
        if self.backend == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
            self._vectorizer.fit(corpus)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.backend == "st":
            vecs = self._model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        else:
            vecs = self._vectorizer.transform(texts).toarray()
            vecs = _l2_normalise(vecs)
        return vecs.tolist()

    def embed_query(self, text: str) -> list[float]:
        if self.backend == "st":
            prefix = BGE_QUERY_PREFIX if "bge" in self.model_name.lower() else ""
            vec = self._model.encode([prefix + text], normalize_embeddings=True)[0]
            return vec.tolist()
        return self.embed_documents([text])[0]


def _l2_normalise(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms
