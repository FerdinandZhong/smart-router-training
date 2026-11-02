"""Training dashboard: serves the page and a small Ray-backed job API. Binds loopback only."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from amp.cluster_ready import fetch_nodes, gpu_nodes, token
from amp.jobs import build_submission, cluster_address, load_config

SUBMISSION_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}')
KINDS = ('cluster_smoke', 'sft', 'grpo')
IMPLEMENTED = {'cluster_smoke'}
SMOKE_CONFIG = 'configs/training/cluster-smoke.json'
NEED_GPU_NODES = 2


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def now():
    return datetime.now(timezone.utc).isoformat()


def connection(root):
    """Explicit 503s; the API key itself is never returned, logged or stored."""
    api_key = token()
    if not api_key:
        raise ApiError(503, 'API key unavailable: CDSW_APIV2_KEY or CML_API_KEY is not set for this application')
    try:
        return api_key, cluster_address(root)
    except (OSError, ValueError, RuntimeError):
        raise ApiError(503, 'ray_cluster_info.json is missing or has no HTTPS head URL; launch the cluster first') from None


def ray_client(root):
    api_key, address = connection(root)
    from ray.job_submission import JobSubmissionClient
    return JobSubmissionClient(address, headers={'Authorization': f'Bearer {api_key}'})


def ray_nodes(root):
    api_key, _ = connection(root)
    return fetch_nodes(root, api_key)


def smoke_gate(root, alive_node_ids):
    """Run id of a passed GPU smoke whose workers ran on distinct nodes Ray reports alive now, else None."""
    for success in sorted(root.glob('training-runs/*/SUCCESS.json')):
        run = success.parent
        try:
            config = json.loads((run / 'run-manifest.json').read_text()).get('config', {})
            result = json.loads(success.read_text())
            workers = config['num_workers']
            ids = {json.loads((run / f'initial-worker-{rank}.json').read_text())['ray_node_id'] for rank in range(workers)}
        except (OSError, ValueError, AttributeError, KeyError, TypeError):
            continue
        if (config.get('purpose') == 'infrastructure_smoke' and config.get('use_gpu') is True
                and isinstance(result, dict) and isinstance(result.get('initial'), dict) and isinstance(result.get('resume'), dict)
                and len(ids) == workers >= NEED_GPU_NODES and ids <= set(alive_node_ids)):
            return run.name
    return None


def status_of(status):
    return str(getattr(status, 'value', status))  # Ray's JobStatus enum or a plain string


class Dashboard:
    def __init__(self, root, client=None, nodes=None):
        self.root = Path(root).resolve()
        self.client = client or (lambda: ray_client(self.root))
        self.nodes = nodes or (lambda: ray_nodes(self.root))

    def under_root(self, value):
        try:
            path = (self.root / value).resolve()
        except (TypeError, ValueError):
            raise ApiError(400, 'Invalid path') from None
        if self.root not in (path, *path.parents):
            raise ApiError(400, f'Path is outside the project root: {value}')
        return path

    def job_dir(self, submission_id):
        if not SUBMISSION_ID.fullmatch(submission_id):
            raise ApiError(400, 'Submission ID must contain only letters, digits, underscores and hyphens')
        return self.root / 'training-jobs' / submission_id

    def event(self, submission_id, state, detail=None):
        with (self.job_dir(submission_id) / 'events.jsonl').open('a') as log:
            log.write(json.dumps({'at': now(), 'state': state, 'detail': detail}) + '\n')

    def events(self, submission_id):
        try:
            return [json.loads(line) for line in (self.job_dir(submission_id) / 'events.jsonl').read_text().splitlines()]
        except OSError:
            return []

    def record(self, submission_id):
        try:
            return json.loads((self.job_dir(submission_id) / 'job.json').read_text())
        except OSError:
            raise ApiError(404, 'Unknown job') from None

    def view(self, record, ray_status):
        """Status is the Ray-observed one; a transition is logged once when first seen."""
        events = self.events(record['submission_id'])
        if ray_status is None:
            ray_status = 'NOT_SUBMITTED' if any(e['state'] == 'rejected' for e in events) else 'UNKNOWN'
        elif not events or events[-1]['state'] != ray_status:
            self.event(record['submission_id'], ray_status)
        return {**record, 'status': ray_status, 'events': events}

    def cluster(self):
        nodes = self.nodes()
        alive = gpu_nodes(nodes)
        gate = smoke_gate(self.root, [n.get('node_id') for n in alive])
        ready = len(alive) >= NEED_GPU_NODES
        why_not = f'Needs {NEED_GPU_NODES} alive GPU nodes; Ray reports {len(alive)}'
        launch = {'cluster_smoke': None if ready else why_not}
        for kind in ('sft', 'grpo'):
            launch[kind] = ('Cluster smoke has not passed' if not gate else 'Trainer not implemented'
                            if kind not in IMPLEMENTED else None if ready else why_not)
        return {'connected': True, 'head_url_present': True, 'gpu_nodes_alive': len(alive),
                'nodes': [{'node_id': n.get('node_id'), 'node_type': n.get('node_type'), 'alive': bool(n.get('alive')),
                           'gpus': (n.get('resources') or {}).get('GPU', 0)} for n in nodes],
                'smoke_gate': {'passed': bool(gate), 'run_id': gate}, 'launch': launch}

    def jobs(self):
        ray = {j.submission_id: status_of(j.status) for j in self.client().list_jobs()}
        records = [self.record(p.parent.name) for p in (self.root / 'training-jobs').glob('*/job.json')
                   if SUBMISSION_ID.fullmatch(p.parent.name)]
        records.sort(key=lambda r: r['created_at'], reverse=True)
        return {'jobs': [self.view(r, ray.get(r['submission_id'])) for r in records]}

    def job(self, submission_id):
        record = self.record(submission_id)
        try:
            status = status_of(self.client().get_job_status(submission_id))
        except ApiError:
            raise
        except Exception:
            status = None  # Ray does not know this ID (never submitted, or purged)
        return self.view(record, status)

    def logs(self, submission_id):
        self.record(submission_id)
        return {'logs': self.client().get_job_logs(submission_id)[-200_000:]}

    def stop(self, submission_id):
        self.record(submission_id)
        stopped = bool(self.client().stop_job(submission_id))
        self.event(submission_id, 'stop_requested', {'accepted': stopped})
        return {'stopped': stopped}

    def config_paths(self, config):
        """Path-valued fields of a UI job config; hub repositories and splits are not paths."""
        weights, dataset = config.get('weights') or {}, config.get('dataset') or {}
        paths = [weights.get('adapter')]
        if weights.get('source') == 'checkpoint':
            paths.append(weights.get('location'))
        if dataset.get('source') == 'file':
            paths += [dataset.get('location'), dataset.get('validation')]
        return [p for p in paths if p]

    def submit(self, body):
        kind, submission_id, config = body.get('kind'), body.get('submission_id'), body.get('config') or {}
        if kind not in KINDS or not isinstance(submission_id, str) or not isinstance(config, dict):
            raise ApiError(400, 'Expected kind (cluster_smoke, sft or grpo), submission_id and an object config')
        directory = self.job_dir(submission_id)
        if kind == 'cluster_smoke':
            config = {'config_path': config.get('config_path') or SMOKE_CONFIG}
            if not isinstance(config['config_path'], str):
                raise ApiError(400, 'config_path must be a string')
            config_path = self.under_root(config['config_path'])
            try:
                smoke = load_config(config_path)
            except (OSError, ValueError) as error:
                raise ApiError(400, str(error)) from None
            from smart_router.data.pilot_bundle import validate_bundle
            try:
                validate_bundle(self.under_root(smoke['dataset']))
            except (OSError, ValueError) as error:
                raise ApiError(400, f'Dataset validation failed: {error}') from None
            self.under_root(Path(smoke['output_dir']) / submission_id)  # the trainer writes here
        else:
            if config.get('method') != kind:
                raise ApiError(400, 'config.method must match kind')
            for path in self.config_paths(config):
                self.under_root(path)
        client = self.client()
        if directory.exists() or any(j.submission_id == submission_id for j in client.list_jobs()):
            raise ApiError(409, 'Submission ID already exists; choose a new ID')
        alive_nodes = gpu_nodes(self.nodes())
        gate = smoke_gate(self.root, [n.get('node_id') for n in alive_nodes])
        if kind == 'cluster_smoke':
            alive = len(alive_nodes)
            if alive < NEED_GPU_NODES:
                raise ApiError(409, f'Needs {NEED_GPU_NODES} alive GPU nodes; Ray reports {alive}')
        elif not gate:
            raise ApiError(409, 'Cluster smoke has not passed')
        try:
            directory.mkdir(parents=True)  # the claim: job.json is written once and never replaced
        except FileExistsError:
            raise ApiError(409, 'Submission ID already exists; choose a new ID') from None
        (directory / 'job.json').write_text(json.dumps(
            {'schema_version': 1, 'submission_id': submission_id, 'kind': kind, 'created_at': now(), 'config': config},
            indent=2) + '\n')
        if kind not in IMPLEMENTED:
            self.event(submission_id, 'rejected', 'trainer not implemented')
            raise ApiError(409, 'trainer not implemented')
        try:
            client.submit_job(**build_submission(self.root, config_path, submission_id, smoke.get('collective_env'),
                                                 timeout_seconds=smoke['job_timeout_seconds']))
        except Exception as error:
            # Client exception text can echo request headers; return and record only the type.
            self.event(submission_id, 'submit_failed', type(error).__name__)
            raise ApiError(502, f'Submission failed ({type(error).__name__}); check the Ray head and dashboard logs') from None
        self.event(submission_id, 'submitted')
        return self.job(submission_id)


def make_handler(dashboard):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, payload, kind='application/json'):
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(code)
            self.send_header('Content-Type', kind + '; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def guard(self):
            length = int(self.headers.get('Content-Length') or 0)
            raw = self.rfile.read(length) if 0 < length <= 1_000_000 else b''  # drain before any early reply
            if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                raise ApiError(415, 'Content-Type must be application/json')
            # A cross-site page cannot set this header without a CORS preflight, which is never granted.
            # Host may differ behind the CAI ingress, so Origin/Host equality is not relied on.
            if self.headers.get('X-Training-Dashboard') != '1':
                raise ApiError(403, 'Same-origin requests only')
            try:
                body = json.loads(raw)
            except ValueError:
                body = None
            if not isinstance(body, dict):
                raise ApiError(400, 'Expected a JSON object body of at most 1 MB')
            return body

        def route(self, method):
            path = urlsplit(self.path).path
            match = re.fullmatch(r'/api/jobs/([^/]+)(?:/(logs|stop))?', path)
            if method == 'GET' and path in ('/', '/index.html'):
                return 200, (ROOT / 'docs/training-demo/dashboard.html').read_bytes(), 'text/html'
            if method == 'GET' and path == '/api/cluster':
                return 200, dashboard.cluster(), None
            if method == 'GET' and path == '/api/jobs':
                return 200, dashboard.jobs(), None
            if method == 'GET' and match and match[2] in (None, 'logs'):
                return 200, (dashboard.logs if match[2] else dashboard.job)(match[1]), None
            if method == 'POST' and path == '/api/jobs':
                return 201, dashboard.submit(self.guard()), None
            if method == 'POST' and match and match[2] == 'stop':
                self.guard()
                return 200, dashboard.stop(match[1]), None
            raise ApiError(404, 'Not found')

        def handle_method(self, method):
            try:
                code, payload, kind = self.route(method)
            except ApiError as error:
                code, payload, kind = error.status, {'error': error.message}, None
            except Exception as error:
                code, payload, kind = 502, {'error': f'Ray request failed: {type(error).__name__}'}, None
            self.send(code, payload, kind or 'application/json')

        def do_GET(self):
            self.handle_method('GET')

        def do_POST(self):
            self.handle_method('POST')

        def log_message(self, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=int(os.getenv('CDSW_APP_PORT', '8096')))
    args = parser.parse_args()
    print(f'Dashboard: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(Dashboard(ROOT))).serve_forever()


if __name__ == '__main__':
    main()
