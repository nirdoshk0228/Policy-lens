"""Golden question sets. Import this BEFORE anything that imports config,
because choosing 'demo' points the data folder at tests/fixtures."""
import os
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
SETS = {
    "sbi": {"golden": HERE / "golden_sbi.jsonl", "data_dir": None},                    # your data/ folder
    "demo": {"golden": HERE / "golden_demo.jsonl", "data_dir": ROOT / "tests" / "fixtures"},
}


def choose(name: str) -> Path:
    s = SETS[name]
    if s["data_dir"]:
        os.environ["POLICYLENS_DATA_DIR"] = str(s["data_dir"])
    return s["golden"]
