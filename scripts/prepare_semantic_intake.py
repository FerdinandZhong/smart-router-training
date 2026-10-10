#!/usr/bin/env python3
"""Repository entrypoint for pinned, unreviewed semantic retrieval intake."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smart_router.semantic_intake import main

if __name__ == "__main__":
    main()
