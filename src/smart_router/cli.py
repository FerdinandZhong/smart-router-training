"""CLI for offline customer dataset construction."""

import argparse
import json
from pathlib import Path
import sys

from smart_router.data.prepare import assign_splits, audit, import_records, load_config, write_bundle
from smart_router.schemas import DataError, TaskSpec


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("audit", "prepare"):
        cmd = sub.add_parser(command)
        cmd.add_argument("--config", required=True, type=Path)
        cmd.add_argument("--project-root", type=Path, default=Path.cwd())
        if command == "prepare":
            cmd.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        records, source = import_records(config, args.project_root)
        if args.command == "audit":
            report = audit(records, TaskSpec.from_dict(config["task"]))
        else:
            records = assign_splits(records, config["dataset"].get("split"))
            report = write_bundle(config, records, source, args.output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (DataError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"Dataset error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
