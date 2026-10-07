"""Bounded concurrent gateway calls compatible with existing annotation receipts."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import time

from smart_router.annotation import backends
from smart_router.annotation.pipeline import VERSION, atomic_json, canonical_json, digest, read_jsonl

PRICES = {'gemini-3.1-flash-lite': (.25, 1.5), 'gpt-5.6-luna': (.2, 1.2),
          'gpt-5.6-sol': (4, 20), 'gpt-5.6-terra': (2, 12), 'gpt-5.4': (2.5, 15)}


def usage_cost(model, usage):
    incoming = usage.get('input_tokens', usage.get('prompt_tokens'))
    outgoing = usage.get('output_tokens', usage.get('completion_tokens'))
    if type(incoming) is not int or type(outgoing) is not int or min(incoming, outgoing) < 0:
        return None
    a, b = PRICES[model]
    return (incoming * a + outgoing * b) / 1_000_000


class Budget:
    def __init__(self, path, limit):
        self.path = Path(path)
        self.events = read_jsonl(self.path) if self.path.exists() else []
        self.lock = threading.Lock()
        self.limit = limit

    def committed(self):
        reserves = {e['key']: e['amount'] for e in self.events if e['event'] == 'reserve'}
        for e in self.events:
            if e['event'] == 'settle':reserves[e['key']] = e['amount']
        return sum(reserves.values())

    def append(self, event):
        with self.path.open('a') as f:
            f.write(canonical_json(event) + '\n'); f.flush()
        self.events.append(event)

    def reserve(self, key, amount):
        with self.lock:
            if any(e['key'] == key and e['event'] == 'reserve' for e in self.events):
                raise RuntimeError('Interrupted request reservation exists; audit before retrying')
            if self.committed() + amount > self.limit:
                raise RuntimeError('Campaign cost ceiling reached; no request sent')
            self.append({'event': 'reserve', 'key': key, 'amount': amount, 'time': time.time()})

    def settle(self, key, amount):
        with self.lock:self.append({'event': 'settle', 'key': key, 'amount': amount, 'time': time.time()})


class GatewayRunner:
    def __init__(self, output, limit=150, requests_per_minute=0, retry_errors=False):
        self.output = Path(output); self.output.mkdir(parents=True, exist_ok=True)
        self.calls = self.output / 'calls'; self.calls.mkdir(exist_ok=True)
        self.budget = Budget(self.output / 'cost-ledger.jsonl', limit)
        self.lock = threading.Lock()
        self.rate_lock = threading.Lock(); self.next_start = 0.0
        self.interval = 60 / requests_per_minute if requests_per_minute else 0
        self.stop = threading.Event(); self.retry_errors = retry_errors

    def invoke(self, model, system, user, context):
        body = backends.request_body(model, system, user)
        key = digest({'pipeline_version': VERSION, 'model': model, 'body': body, 'context': context})
        path = self.calls / (key + '.json')
        previous = json.loads(path.read_text()) if path.exists() else None
        if previous is None and any(e['key'] == key and e['event'] == 'reserve' for e in self.budget.events):
            attempts = [x['attempt'] for x in read_jsonl(self.output / 'attempts.jsonl') if x['key'] == key]
            previous = {'status':'error', 'error':'interrupted_request', 'attempt':max(attempts, default=1), 'key':key}
        if previous and (previous['status'] == 'ok' or not self.retry_errors or previous.get('error') not in ['http_429','http_500','http_502','http_503','http_504','transport_error','request_timeout','interrupted_request'] or previous['attempt'] >= 3):return previous
        attempt = previous['attempt'] + 1 if previous else 1
        with self.rate_lock:
            delay = max(0, self.next_start - time.monotonic())
            self.next_start = time.monotonic() + delay + self.interval
        if self.stop.wait(delay):raise RuntimeError('Candidate phase stopped; no request sent')
        reservation_key = key if attempt == 1 else key + ':' + str(attempt)
        input_rate, output_rate = PRICES[model['model']]
        # Conservative byte-based token allowance plus framing; prices are the supplied gateway rates.
        reservation = ((len(canonical_json(body).encode()) + 1024) * input_rate + model['max_output_tokens'] * output_rate) / 1_000_000
        self.budget.reserve(reservation_key, reservation)
        with self.lock:
            with (self.output / 'attempts.jsonl').open('a') as f:
                f.write(canonical_json({'key':key, 'attempt':attempt, 'reserved_output_tokens':model['max_output_tokens'], 'time':time.time()}) + '\n');f.flush()
        result = {'key':key, 'context':context, 'requested_model':model['model'], 'api':model['api'], 'attempt':attempt}
        started = time.monotonic()
        try:
            result.update(backends.call(model, body, context, {}));result['status'] = 'ok'
        except backends.CallError as exc:
            result.update(status='error', error=str(exc))
        result['latency_seconds'] = time.monotonic() - started
        actual = usage_cost(model['model'], result.get('usage', {}))
        result['estimated_cost_usd'] = actual if actual is not None else reservation
        result['cost_basis'] = 'gateway_configured_token_rates_no_cache_discount' if actual is not None else 'conservative_reservation_usage_unavailable'
        atomic_json(self.calls / f'{key}.attempt-{attempt}.json', result);atomic_json(path, result)
        self.budget.settle(reservation_key, result['estimated_cost_usd'])
        if result.get('error') == 'http_429':
            self.stop.set()
            raise RuntimeError('Gateway returned HTTP 429; phase stopped, receipts preserved')
        return result


def model_spec(class_id, name, credential_file):
    is_fast = class_id == 'FAST'
    return {'id':class_id.lower(), 'class_id':class_id, 'model':name,
            'api':'chat_completions' if is_fast else 'responses',
            'base_url':'https://ai-gateway.cloudops.cloudera.com',
            'api_key_file':str(Path(credential_file).expanduser().resolve()),
            'max_output_tokens':2048, 'timeout_seconds':90,
            'generation':{'response_format':{'type':'json_object'}} if is_fast else
                {'text':{'format':{'type':'json_object'}}, 'reasoning':{'effort':'low'}}}
