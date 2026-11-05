"""Tests run offline on the two fictional demo policies in tests/fixtures,
copied to a temp folder so your own data/ folder is never touched."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
_tmp = Path(tempfile.mkdtemp(prefix="policylens_test_"))
shutil.copytree(ROOT / "tests" / "fixtures" / "chunks", _tmp / "chunks")

os.environ["POLICYLENS_DATA_DIR"] = str(_tmp)   # inherited by the MCP server subprocess too
os.environ["EMBED_BACKEND"] = "tfidf"
os.environ["RERANK_MODEL"] = ""
sys.path.insert(0, str(ROOT))
