#!/usr/bin/env python3
"""Prepare the customer-scoped Laya/GLiNER annotation package."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from smart_router.semantic_scoped_data import main
if __name__ == '__main__':
    main()
