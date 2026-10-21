#!/usr/bin/env python3
"""Wait for the active bounded campaign, then validate caches and retry failures once."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
status = ROOT / "data/semantic-research/review-work-20261010-v2/opus-5-5-review-20261019-v1/status.json"
while True:
    current = json.loads(status.read_text())
    if current["state"] == "complete":
        break
    time.sleep(15)
# Validated cached reviews are reused, so this only calls the model for unresolved records.
subprocess.run([sys.executable, str(ROOT / "scripts/review_semantic_with_opus.py"), "--limit", "80"], cwd=ROOT, check=True)
print("OPUS_REVIEW_FINISHED", status.read_text(), flush=True)
