"""One recorded-state compatibility check, in FAST/GENERAL/REASONING order."""
import argparse
import json
from pathlib import Path
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from smart_router.annotation.backends import call, request_body, CallError
from smart_router.annotation.pipeline import CANDIDATE_SYSTEM
from smart_router.annotation.checks import check_action
from smart_router.schemas import canonical_json, model_input


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'data/prepared/gateway-pilot-v1')
    parser.add_argument('--output', type=Path, default=ROOT / '.amp-state/gateway-candidate-preflight.json')
    parser.add_argument('--api-key-file', default='~/tokens/litellm_key_applied_ai')
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Use a new receipt path; preflight is not implicitly rerun')
    record = json.loads((args.dataset / 'records.jsonl').read_text().splitlines()[0])
    mapping = json.loads((args.dataset / 'manifest.json').read_text())['source']['candidate_mapping']
    results = []
    for cls, name in mapping.items():
        model = {'id': cls.lower(), 'class_id': cls, 'model': name,
                 'api': 'chat_completions' if cls == 'FAST' else 'responses',
                 'base_url': 'https://ai-gateway.cloudops.cloudera.com',
                 'api_key_file': args.api_key_file, 'max_output_tokens': 2048, 'timeout_seconds': 90,
                 'generation': {'response_format': {'type': 'json_object'}} if cls == 'FAST' else
                    {'text': {'format': {'type': 'json_object'}}, 'reasoning': {'effort': 'low'}}}
        context = {'role': 'candidate', 'example_id': record['example_id'], 'candidate': model['id'], 'trial': 0}
        start = time.monotonic(); result = {'class_id': cls, 'requested_model': name, 'api': model['api'], 'example_id': record['example_id'], 'generation': model['generation']}
        try:
            result.update(call(model, request_body(model, CANDIDATE_SYSTEM, canonical_json(model_input(record))), context, {}))
            result.update(status='ok', deterministic_check=check_action(record, result['text']))
        except CallError as exc:
            result.update(status='error', error=str(exc))
        result['latency_seconds'] = time.monotonic() - start;results.append(result)
        args.output.parent.mkdir(parents=True, exist_ok=True);args.output.write_text(json.dumps(results, indent=2))
        print(json.dumps({k: result.get(k) for k in ['class_id', 'status', 'error', 'latency_seconds', 'usage', 'deterministic_check']}), flush=True)


if __name__ == '__main__':main()
