"""Reannotate the original states with gateway candidates and an independent Sonnet judge."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from smart_router.annotation import gateway_campaign
from smart_router.annotation import backends
from smart_router.annotation.backends import request_body
from smart_router.annotation.pipeline import (
    Runner, VERSION, JUDGE_RESPONSE_FORMAT, atomic_json, digest, plan, prepare, run, run_lock,
)
from smart_router.data.pilot_bundle import validate_bundle
from export_smoke_training_data import export

CONFIG = ROOT / 'configs/annotation/pilot-300-gateway-sonnet-v1.json'
OUT = ROOT / 'runs/pilot-300-gateway-sonnet-v1'
SOURCE = ROOT / 'data/prepared/pilot-300-gateway-sonnet-v1'
DEST = ROOT / 'data/pilot/pilot-300-gateway-sonnet-v1'


def install_rate_diagnostics():
    """Log rate metadata without provider bodies, credentials or request inputs."""
    original = backends.urllib.request.build_opener

    class Opener:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def open(self, *args, **kwargs):
            try:
                return self.wrapped.open(*args, **kwargs)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    headers = {k: v for k, v in exc.headers.items()
                               if 'ratelimit' in k.lower() or k.lower() == 'retry-after'}
                    metadata = {'http_status': 429, 'rate_headers': headers}
                    try:
                        body = json.loads(exc.read())
                        message = str(body.get('error', {}).get('message', '')).lower()
                        metadata['limit_markers'] = [term for term in
                            ['team_member', 'tpm', 'rpm', 'token', 'request', 'budget', 'minute', 'hour']
                            if term in message]
                        metadata['numeric_limits'] = re.findall(r'(?:limit|current|remaining)\s*[:=]\s*(\d+)', message)
                    except (ValueError, AttributeError):
                        pass
                    print(json.dumps(metadata), flush=True)
                raise

    backends.urllib.request.build_opener = lambda *args, **kwargs: Opener(original(*args, **kwargs))


class TokenPacedGateway(gateway_campaign.GatewayRunner):
    """Limit conservative request volume as well as request count."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token_lock = threading.Lock()
        self.next_token_start = 0.0

    def invoke(self, model, system, user, context):
        body = request_body(model, system, user)
        key = digest({'pipeline_version': VERSION, 'model': model, 'body': body, 'context': context})
        path = self.calls / (key + '.json')
        previous = json.loads(path.read_text()) if path.exists() else None
        if previous and (previous['status'] == 'ok' or previous.get('attempt', 0) >= 3):
            return super().invoke(model, system, user, context)
        # Byte-based allowance deliberately overestimates actual tokenizer counts.
        allowance = len(json.dumps(body, ensure_ascii=False).encode()) + 1024 + model['max_output_tokens']
        with self.token_lock:
            delay = max(0, self.next_token_start - time.monotonic())
            self.next_token_start = time.monotonic() + delay + 60 * allowance / 300_000
        if self.stop.wait(delay):
            raise RuntimeError('Phase stopped before token allowance became available')
        result = super().invoke(model, system, user, context)
        if (result.get('error') in {'http_500', 'http_502', 'http_503', 'http_504',
                                   'transport_error', 'request_timeout', 'interrupted_request'}
                and result.get('attempt', 0) < 3):
            return self.invoke(model, system, user, context)
        return result


def supervise(detach=False, requests_per_minute=5, max_invocations=24):
    """Keep the authorized long run alive and archive its verified result."""
    OUT.mkdir(parents=True, exist_ok=True)
    if detach:
        with (OUT / 'supervisor.log').open('a') as log:
            process = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve()), 'supervise',
                                        '--requests-per-minute', str(requests_per_minute),
                                        '--max-invocations', str(max_invocations)],
                                       cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
        atomic_json(OUT / 'supervisor.json', {'pid': process.pid, 'log': 'supervisor.log',
                    'requests_per_minute': requests_per_minute, 'max_invocations': max_invocations})
        print(json.dumps({'supervisor_pid': process.pid, 'output': str(OUT.relative_to(ROOT))}), flush=True)
        return
    retries = 0
    while True:
        lock = OUT / 'run.lock'
        if lock.exists():
            try:
                os.kill(int(lock.read_text().strip()), 0)
                time.sleep(15)
                continue
            except (ProcessLookupError, ValueError):
                pass
        state = json.loads((OUT / 'campaign-state.json').read_text()) if (OUT / 'campaign-state.json').exists() else {}
        if state.get('status') == 'completed':
            manifest = validate_bundle(DEST)
            summary = json.loads((OUT / 'campaign-summary.json').read_text())
            status = ROOT / 'docs/status/2026-10-06-pilot-300-gateway-sonnet.md'
            status.write_text('# Original pilot Sonnet reannotation — 2026-10-06\n\n'
                              'Verified final artifact: `data/pilot/pilot-300-gateway-sonnet-v1`.\n\n'
                              'All original inputs and split assignments were preserved. The gateway\n'
                              'candidate mapping is Flash Lite / Luna / Sol. The independent judge is\n'
                              '`global.anthropic.claude-sonnet-5`, with thinking disabled.\n\n'
                              '```json\n' + json.dumps(summary, indent=2) + '\n```\n\n'
                              'Silver local-step observations only. Unknowns remain masked. No executable\n'
                              'replay, calibration, combined dataset or new training was performed.\n'
                              'The provisional Sonnet cost allowance is not verified gateway billing.\n')
            todo = ROOT / 'TODO.md'
            old = '- [ ] Complete 900 candidate responses and 900 Sonnet judgments; validate a new\n  `pilot-300-gateway-sonnet-v1` bundle. Run started with resumable receipts.'
            used = {'candidate': set(), 'judge': set()}
            for line in (OUT / 'silver_labels.jsonl').read_text().splitlines():
                label = json.loads(line)
                for evidence in label['classes'].values():
                    for trial in evidence['trials']:
                        used['candidate'].add(trial['candidate_call'])
                        used['judge'].update(v['call'] for v in trial['judges'])
            successes = Counter({role: sum(json.loads((OUT / 'calls' / (key + '.json')).read_text())['status'] == 'ok'
                                           for key in keys) for role, keys in used.items()})
            if successes['candidate'] == 900 and successes['judge'] == 900:
                todo.write_text(todo.read_text().replace(old,
                    '- [x] Complete 900 candidate responses and 900 Sonnet judgments; validate the new\n'
                    '  `pilot-300-gateway-sonnet-v1` bundle. See [dated evidence](docs/status/2026-10-06-pilot-300-gateway-sonnet.md).'))
            atomic_json(OUT / 'supervisor-result.json', {'status': 'completed', 'splits': manifest['splits'],
                                                        'successful_calls': dict(successes), 'evidence': str(status.relative_to(ROOT))})
            print('Verified final bundle and archived evidence.', flush=True)
            return
        if retries >= max_invocations:
            atomic_json(OUT / 'supervisor-result.json', {'status': 'stopped',
                'reason': 'campaign_invocation_limit', 'invocations': retries, 'receipts_preserved': True})
            print('Supervisor reached its invocation limit; receipts preserved.', flush=True)
            return
        if state.get('status') == 'failed':
            if state.get('error_reason') == 'estimated_cost_ceiling':
                atomic_json(OUT / 'supervisor-result.json', {'status': 'stopped',
                    'reason': 'estimated_cost_ceiling', 'receipts_preserved': True})
                print('Estimated cost ceiling reached; no further requests authorized by this run.', flush=True)
                return
            # Shared allowance can remain exhausted beyond the suggested retry delay.
            cooldown = min(900, 120 * 2 ** min(max(retries - 1, 0), 3)) if retries else 0
            if cooldown:
                atomic_json(OUT / 'supervisor-progress.json', {'status': 'cooldown',
                            'seconds': cooldown, 'invocations': retries})
                print(json.dumps({'supervisor': 'cooldown', 'seconds': cooldown}), flush=True)
                for _ in range(cooldown // 15):
                    time.sleep(15)
        retries += 1
        atomic_json(OUT / 'supervisor-progress.json', {'status': 'running', 'invocations': retries,
                    'requests_per_minute': requests_per_minute})
        result = subprocess.run([sys.executable, '-u', str(Path(__file__).resolve()),
                                 'all', '--requests-per-minute', str(requests_per_minute), '--diagnose-rate-limits'], cwd=ROOT)
        if result.returncode:
            print('Campaign exited; checking resumable state before retry.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['plan', 'check', 'all', 'supervise', 'schema-check'])
    parser.add_argument('--detach', action='store_true')
    parser.add_argument('--diagnose-rate-limits', action='store_true')
    parser.add_argument('--requests-per-minute', type=int, default=5)
    parser.add_argument('--max-invocations', type=int, default=24)
    args = parser.parse_args()
    if args.requests_per_minute < 1 or args.max_invocations < 1:
        parser.error('Pacing and invocation limits must be positive')
    if args.diagnose_rate_limits:
        install_rate_diagnostics()
    if args.operation == 'supervise':
        supervise(args.detach, args.requests_per_minute, args.max_invocations)
        return
    frozen = prepare(CONFIG)
    if args.operation == 'plan':
        print(json.dumps(plan(frozen), indent=2))
        return
    gateway_campaign.PRICES.update(frozen['config']['cost_policy']['input_output_rates_per_million'])
    OUT.mkdir(parents=True, exist_ok=True)
    if args.operation == 'schema-check':
        model = frozen['config']['judges'][0]
        model['generation']['response_format'] = JUDGE_RESPONSE_FORMAT
        gateway = TokenPacedGateway(OUT / 'schema-check', 5, 10, True)
        runner = Runner(frozen, OUT)
        def invoke(spec, system, user, context):
            if context['role'] == 'candidate':
                cached = gateway_campaign.GatewayRunner(OUT, 75, 10, False)
                return cached.invoke(spec, system, user, context)
            return gateway.invoke(spec, system, user, context)
        runner.invoke = invoke
        trial = runner.trial(frozen['records'][0], frozen['config']['candidates'][0], 0)
        atomic_json(OUT / 'schema-check/result.json', trial)
        print(json.dumps(trial), flush=True)
        if not trial['judges'] or trial['judges'][0].get('unknown_reason') not in {None, 'abstention_or_low_confidence'}:
            raise RuntimeError('Strict schema check failed')
        return
    with run_lock(OUT):
        identity = digest(frozen)
        if (OUT / 'run.json').exists():
            if json.loads((OUT / 'run.json').read_text())['run_hash'] != identity:
                raise ValueError('Frozen run changed; use a new output directory')
        else:
            atomic_json(OUT / 'inputs.json', frozen)
            atomic_json(OUT / 'run.json', {'run_hash': identity, 'pipeline_version': VERSION, 'plan': plan(frozen)})
        if args.requests_per_minute < 1:
            raise ValueError('requests-per-minute must be positive')
        gateway = TokenPacedGateway(OUT, 75, args.requests_per_minute, True)
        runner = Runner(frozen, OUT)
        runner.invoke = gateway.invoke
        records = frozen['records'][:1] if args.operation == 'check' else frozen['records']
        for candidate in frozen['config']['candidates']:
            atomic_json(OUT / 'campaign-state.json', {'status': 'running', 'phase': candidate['class_id']})
            jobs = [(record, candidate) for record in records]
            counts = Counter()
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = [pool.submit(runner.trial, record, model, 0) for record, model in jobs]
                for index, future in enumerate(as_completed(futures), 1):
                    trial = future.result()
                    counts[str(trial['verdict'])] += 1
                    if args.operation == 'check':
                        atomic_json(OUT / (candidate['id'] + '-compatibility.json'), trial)
                        if not trial['judges'] or trial['judges'][0].get('unknown_reason'):
                            raise RuntimeError('Judge compatibility failed; inspect private receipt')
                    if index % 10 == 0 or index == len(jobs):
                        progress = {'class': candidate['class_id'], 'completed': index, 'total': len(jobs),
                                    'verdicts': dict(counts), 'estimated_commitment_usd': gateway.budget.committed()}
                        atomic_json(OUT / 'progress.json', progress)
                        print(json.dumps(progress), flush=True)
            atomic_json(OUT / (candidate['id'] + '-phase.json'), dict(counts))
    if args.operation == 'check':
        return
    with patch('smart_router.annotation.backends.call', side_effect=AssertionError('Finalization cannot call network')):
        report = run(frozen, OUT, live=True)
    if DEST.exists():
        manifest = validate_bundle(DEST)
    else:
        manifest = export(SOURCE, [OUT / 'silver_labels.jsonl'], DEST,
                          dataset_id=DEST.name, purpose='pilot_training')
        manifest['annotation_policy'] = {'judge': frozen['config']['judges'][0]['model'],
                                         'confidence_threshold': .8, 'trials': 1,
                                         'candidate_mapping': manifest['source']['candidate_mapping']}
        atomic_json(DEST / 'manifest.json', manifest)
        validate_bundle(DEST)
    old = {json.loads(line)['example_id']: json.loads(line)
           for split in manifest['splits']
           for line in (ROOT / 'data/pilot/pilot-smoke-v1' / (split + '.jsonl')).read_text().splitlines()}
    for split in manifest['splits']:
        for line in (DEST / (split + '.jsonl')).read_text().splitlines():
            row = json.loads(line)
            assert row['input'] == old[row['example_id']]['input']
            assert row['split'] == old[row['example_id']]['split']
    summary = {'artifact': str(DEST.relative_to(ROOT)), 'splits': manifest['splits'],
               'class_support': manifest['class_support'], 'report': report,
               'estimated_commitment_usd': gateway.budget.committed(),
               'cost_policy': frozen['config']['cost_policy'], 'original_inputs_and_splits_verified': True}
    atomic_json(OUT / 'campaign-summary.json', summary)
    atomic_json(OUT / 'campaign-state.json', {'status': 'completed', 'phase': 'exported'})
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if len(sys.argv) > 1 and sys.argv[1] not in {'plan', 'schema-check'}:
            OUT.mkdir(parents=True, exist_ok=True)
            reason = 'estimated_cost_ceiling' if str(exc) == 'Campaign cost ceiling reached; no request sent' else 'campaign_error'
            atomic_json(OUT / 'campaign-state.json', {'status': 'failed', 'error_type': type(exc).__name__,
                                                    'error_reason': reason})
        raise
