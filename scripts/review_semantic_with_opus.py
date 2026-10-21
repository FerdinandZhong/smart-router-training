#!/usr/bin/env python3
"""Run user-delegated Opus 5.5 review of the first 80 semantic pilot samples."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smart_router.semantic_delegated_review import run
from smart_router.semantic_review_ui import ReviewStore

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--limit", type=int, default=80)
parser.add_argument("--output", type=Path, default=ROOT / "data/semantic-research/review-work-20261010-v2/opus-5-5-review-20261019-v1")
args = parser.parse_args()
if not 1 <= args.limit <= 80:
    parser.error("limit must be 1..80")
store = ReviewStore(ROOT / "data/semantic-research/pilot-20261010-v3", ROOT / "data/semantic-research/review-work-20261010-v2", ROOT / "data/semantic-research/baselines-20261010-v3")
config = json.loads((ROOT / "configs/semantic_retrieval/opus-reviewer.json").read_text())
print(json.dumps(run(store, config, args.output, args.limit)), flush=True)
