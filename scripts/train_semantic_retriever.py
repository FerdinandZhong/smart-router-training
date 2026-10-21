#!/usr/bin/env python3
"""Preflight or train the isolated structural semantic retrieval baseline."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smart_router.training.semantic_retriever import main

if __name__ == "__main__":
    main()
