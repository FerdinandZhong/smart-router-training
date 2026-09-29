"""Prepare 300 pre-call states and a ten-state annotation subset from a pinned shard."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smart_router.data.swe_gym import construct

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(construct(args.source, args.output), indent=2))
