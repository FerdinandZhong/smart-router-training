"""Command-line entry point for offline and live annotation."""

import argparse
import json
import sys

from smart_router.annotation.pipeline import plan, prepare, run
from smart_router.schemas import DataError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "candidates", "run"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", help="Required for run; reused to resume unchanged inputs")
    parser.add_argument("--live", action="store_true", help="Allow HTTP model calls or importing real external execution receipts")
    parser.add_argument("--retry-errors", action="store_true", help="Retry cached call errors once this run, within attempt/budget limits")
    args = parser.parse_args(argv)
    if args.command != "plan" and not args.output:
        parser.error("run and candidates require --output")
    try:
        frozen = prepare(args.config)
        result = plan(frozen) if args.command == "plan" else run(frozen, args.output, args.live, args.retry_errors, args.command == "candidates")
        print(json.dumps(result, indent=2))
        return 0
    except (DataError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Annotation error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
