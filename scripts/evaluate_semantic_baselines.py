#!/usr/bin/env python3
"""Run structural candidate-retrieval diagnostics; no label approvals or training."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smart_router.semantic_baselines import main

if __name__ == "__main__":
    main()
