"""Central settings. Everything can be overridden with environment variables (.env)."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:  # optional: load .env if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Where policies, chunks and the vector index live. Tests point this at
# tests/fixtures so your own policies in data/ are never touched.
DATA_DIR = Path(os.getenv("POLICYLENS_DATA_DIR", ROOT / "data")).resolve()
POLICY_DIR = DATA_DIR / "policies"
CHUNK_DIR = DATA_DIR / "chunks"
INDEX_DIR = DATA_DIR / "index"

# Embeddings: "st" = sentence-transformers (real semantic model, needs internet once
# to download), "tfidf" = offline fallback used for quick tests.
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "st")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

# Cross-encoder reranker. Set to "" to disable.
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-base")

# Any OpenAI-compatible chat API: OpenAI, Groq, OpenRouter, Ollama (local) ...
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
