"""
Step B — Hybrid search over all loaded policies.

    question ──► BM25 (exact words)  ──┐
             └─► vector (meaning)    ──┴─► Reciprocal Rank Fusion ──► reranker ──► top k

Why hybrid?
  - Vector search understands "eye lens surgery" ≈ "cataract",
    but is weak on exact codes like "Code-Excl02" or "PED".
  - BM25 nails exact terms but misses synonyms.
  RRF merges the two ranked lists using only the ranks (no score scaling needed):
      score(doc) = Σ 1 / (60 + rank_in_list)

Why a reranker?
  Bi-encoder embeddings compare question and chunk separately (fast, approximate).
  A cross-encoder reads question + chunk *together* and scores the pair — slower
  but more accurate, so we use it only on the ~20 fused candidates.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi

import config
from .embedder import Embedder

RRF_K = 60
STOPWORDS = set(
    "a an the of to in on for and or is are be by with as at from this that it its any all "
    "shall will which who what when how does do my i me under policy".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


def load_all_chunks(chunk_dir: Path = config.CHUNK_DIR) -> list[dict]:
    chunks = []
    for f in sorted(Path(chunk_dir).glob("*.jsonl")):
        chunks.extend(json.loads(line) for line in f.open(encoding="utf-8") if line.strip())
    return chunks


def cite(c: dict) -> str:
    """Human-readable citation used in every answer."""
    loc = c["section"] + (f" > {c['clause']}" if c["clause"] else "")
    pages = c["pages"] if isinstance(c["pages"], list) else [int(p) for p in str(c["pages"]).split(",")]
    p = f"p.{pages[0]}" if len(pages) == 1 else f"pp.{pages[0]}-{pages[-1]}"
    return f"{c['policy_name']}, {loc}, {p}"


class PolicyIndex:
    def __init__(
        self,
        embed_backend: str = config.EMBED_BACKEND,
        embed_model: str = config.EMBED_MODEL,
        rerank_model: str = config.RERANK_MODEL,
        chunk_dir: Path = config.CHUNK_DIR,
        index_dir: Path = config.INDEX_DIR,
    ):
        self.chunk_dir = Path(chunk_dir)
        self.index_dir = Path(index_dir)
        self.embedder = Embedder(embed_backend, embed_model)
        self.reranker = _load_reranker(rerank_model)
        self.chunks: list[dict] = []
        self.by_id: dict[str, dict] = {}
        self.bm25: BM25Okapi | None = None
        self.collection = None
        self.refresh()

    # ---------- building ----------
    def refresh(self) -> None:
        """(Re)load chunks; rebuild the vector index only if chunks or model changed."""
        self.chunks = load_all_chunks(self.chunk_dir)
        self.by_id = {c["chunk_id"]: c for c in self.chunks}
        if not self.chunks:
            return

        texts = [c["text_for_embedding"] for c in self.chunks]
        self.bm25 = BM25Okapi([tokenize(t) for t in texts])  # cheap, rebuilt in memory
        self.embedder.fit(texts)

        client = chromadb.PersistentClient(path=str(self.index_dir / "chroma"))
        fingerprint = self._fingerprint()
        manifest = self.index_dir / "manifest.json"
        old = json.loads(manifest.read_text()) if manifest.exists() else {}

        if old.get("fingerprint") == fingerprint:
            self.collection = client.get_collection("policylens")
            return

        # Something changed (new PDF / different model) -> rebuild vectors
        try:
            client.delete_collection("policylens")
        except Exception:
            pass
        self.collection = client.create_collection("policylens", metadata={"hnsw:space": "cosine"})
        vectors = self.embedder.embed_documents(texts)
        for i in range(0, len(self.chunks), 256):
            batch = self.chunks[i : i + 256]
            self.collection.add(
                ids=[c["chunk_id"] for c in batch],
                embeddings=vectors[i : i + 256],
                documents=[c["text"] for c in batch],
                metadatas=[
                    {"policy_name": c["policy_name"], "section": c["section"], "clause": c["clause"],
                     "pages": ",".join(map(str, c["pages"]))}
                    for c in batch
                ],
            )
        self.index_dir.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"fingerprint": fingerprint, "n_chunks": len(self.chunks),
                                        "embedder": self.embedder.id}, indent=2))

    def _fingerprint(self) -> str:
        h = hashlib.sha256(self.embedder.id.encode())
        for c in self.chunks:
            h.update(c["chunk_id"].encode())
            h.update(c["text_for_embedding"].encode())
        return h.hexdigest()

    # ---------- searching ----------
    def policies(self) -> list[str]:
        return sorted({c["policy_name"] for c in self.chunks})

    def bm25_search(self, query: str, policy: str | None = None, k: int = 20) -> list[str]:
        scores = self.bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        ids = [self.chunks[i]["chunk_id"] for i in order
               if scores[i] > 0 and (policy is None or self.chunks[i]["policy_name"] == policy)]
        return ids[:k]

    def vector_search(self, query: str, policy: str | None = None, k: int = 20) -> list[str]:
        res = self.collection.query(
            query_embeddings=[self.embedder.embed_query(query)],
            n_results=min(k, len(self.chunks)),
            where={"policy_name": policy} if policy else None,
        )
        return res["ids"][0]

    def search(self, query: str, policy: str | None = None, k: int = 5,
               mode: str = "hybrid", rerank: bool = True) -> list[dict]:
        """mode: 'bm25' | 'vector' | 'hybrid'. Returns chunk dicts + score + citation."""
        if not self.chunks:
            return []
        if policy and policy not in self.policies():
            raise ValueError(f"Unknown policy '{policy}'. Loaded: {self.policies()}")

        lists = []
        if mode in ("bm25", "hybrid"):
            lists.append(self.bm25_search(query, policy))
        if mode in ("vector", "hybrid"):
            lists.append(self.vector_search(query, policy))

        fused: dict[str, float] = {}
        for ranked in lists:
            for rank, cid in enumerate(ranked, start=1):
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank)
        candidates = sorted(fused, key=fused.get, reverse=True)[:20]

        if rerank and self.reranker is not None and candidates:
            pairs = [(query, self.by_id[cid]["text_for_embedding"]) for cid in candidates]
            scores = self.reranker.predict(pairs)
            ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
            final = [(cid, float(s)) for cid, s in ranked[:k]]
        else:
            final = [(cid, fused[cid]) for cid in candidates[:k]]

        return [{**self.by_id[cid], "score": round(score, 4), "cite": cite(self.by_id[cid])}
                for cid, score in final]

    def clauses(self, policy: str) -> list[str]:
        seen = []
        for c in self.chunks:
            label = c["section"] + (f" > {c['clause']}" if c["clause"] else "")
            if c["policy_name"] == policy and label not in seen:
                seen.append(label)
        return seen


def _load_reranker(model_name: str):
    if not model_name:
        return None
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder(model_name)
    except Exception as e:  # no internet / library missing -> run without reranker
        # stderr, never stdout: stdout is the MCP protocol channel
        print(f"[policylens] reranker disabled ({type(e).__name__}): continuing with RRF only", file=sys.stderr)
        return None
