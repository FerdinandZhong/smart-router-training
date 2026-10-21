#!/usr/bin/env python3
"""Prepare, audit, or export the isolated semantic retrieval pilot."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smart_router.semantic_pilot import main

if __name__ == "__main__":
    main()
