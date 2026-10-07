"""Discover model IDs from the configured OpenAI-compatible gateway."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='https://ai-gateway.cloudops.cloudera.com')
    parser.add_argument('--api-key-env', default='OPENAI_API_KEY')
    parser.add_argument('--api-key-file', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    key = args.api_key_file.expanduser().read_text().strip() if args.api_key_file else os.environ.get(args.api_key_env, '')
    if not key:
        parser.error(f'Missing credential: set {args.api_key_env} or use --api-key-file; never pass the key as a command argument')
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url=args.base_url, timeout=15, max_retries=0)
    try:
        ids = sorted({model.id for model in client.models.list()})
    except Exception as exc:
        # SDK exception text can contain request details; report only safe metadata.
        status = getattr(exc, 'status_code', None)
        raise SystemExit(f'Model discovery failed: {type(exc).__name__}; HTTP status {status}') from None
    for model_id in ids:
        print(model_id)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({'base_url': args.base_url,
            'discovered_at': datetime.now(timezone.utc).isoformat(), 'model_ids': ids}, indent=2) + '\n')


if __name__ == '__main__':
    main()
