#!/usr/bin/env python3
"""Generate fixed-judge drafts without changing human review files."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smart_router.semantic_review_ui import ReviewStore
from smart_router.semantic_review_judge import batch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--limit", type=int, default=80)
parser.add_argument("--probe", action="store_true")
parser.add_argument("--model")
parser.add_argument("--scope", choices=["first80", "pilot"], default="first80")
args = parser.parse_args()
if not 1 <= args.limit <= 10000:
    parser.error("limit must be between 1 and 10000")
root = Path.cwd()
store = ReviewStore(root / "data/semantic-research/pilot-20261010-v3", root / "data/semantic-research/review-work-20261010-v2", root / "data/semantic-research/baselines-20261010-v3")
config = json.loads((root / "configs/semantic_retrieval/review-judge.json").read_text())
if args.model:
    config["model"] = args.model
    if args.model.startswith("gpt-"):
        config["api"] = "responses"
        config["generation"] = {"text": {"format": {"type": "json_object"}}, "reasoning": {"effort": "low"}}
if args.probe:
    from smart_router.annotation.backends import call, request_body, CallError
    config.update(max_output_tokens=256, timeout_seconds=45)
    try:
        response = call(config, request_body(config, "Return JSON only.", 'Return {"ok":true}.'), {}, {})
        print(json.dumps(response))
    except CallError as exc:
        print(json.dumps({"error": str(exc)}))
    raise SystemExit()
print(json.dumps(batch(store, config, args.limit, args.scope)), flush=True)
