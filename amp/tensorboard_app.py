"""Provision or serve the authenticated TensorBoard CAI application."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from amp.environment import isolated_environment


def application_spec(root, environment=None):
    env = os.environ if environment is None else environment
    subdomain = env.get('TENSORBOARD_SUBDOMAIN', 'smart-router-tensorboard')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', subdomain):
        raise ValueError('TENSORBOARD_SUBDOMAIN must be a DNS label')
    # Match the CPU runtime already selected for this project's head.
    import yaml
    config = yaml.safe_load((root / 'configs/ray_cluster_config.yaml').read_text())
    return dict(name='Smart Router TensorBoard', script='amp/serve_tensorboard.py',
                cpu=1, memory=2, num_gpus=0,
                runtime_identifier=config['cai']['head_runtime_identifier'],
                subdomain=subdomain, bypass_authentication=False)


def ensure_application(client, project_id, spec):
    existing = [app for app in client.list_applications(project_id)
                if app.subdomain == spec['subdomain']]
    if existing:
        app = existing[0]
        if app.metadata.get('script') != spec['script'] or app.metadata.get('bypass_authentication') is not False:
            raise RuntimeError('Existing subdomain has different script/auth settings; choose another TENSORBOARD_SUBDOMAIN')
        return app
    return client.create_application(project_id=project_id, **spec)


def serve(root=ROOT):
    python = root / '.venv-router-train/bin/python'
    if not python.exists():
        raise RuntimeError('Run amp/setup_training_environment.py first')
    port = int(os.environ['CDSW_APP_PORT'])
    if not 1 <= port <= 65535:
        raise ValueError('Invalid CDSW_APP_PORT')
    logdir = root / 'training-runs'
    logdir.mkdir(exist_ok=True)
    # Keep the PBJ kernel alive. The child owns the HTTP server and fails the app
    # on startup errors. CAI ingress supplies authentication and TLS.
    command = [str(python), '-m', 'tensorboard.main', '--logdir', str(logdir),
               '--host', '0.0.0.0', '--port', str(port), '--reload_interval', '5',
               '--load_fast', 'false']
    print(f'Serving TensorBoard on port {port}; event root: {logdir}', flush=True)
    subprocess.run(command, cwd=root, env=isolated_environment(root, python), check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['plan', 'deploy', 'serve'])
    args = parser.parse_args()
    if args.operation == 'serve':
        serve()
        return
    python = ROOT / '.venv/bin/python'
    if args.operation == 'deploy':
        if not python.exists():
            raise RuntimeError('Run amp/setup_cluster_environment.py first')
        env = isolated_environment(ROOT, python)
        if Path(sys.prefix).resolve() != python.parent.parent.resolve() or any(
            os.environ.get(k) != env.get(k) for k in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONNOUSERSITE')
        ):
            os.execve(str(python), [str(python), str(ROOT / 'amp/tensorboard_app.py'), 'deploy'], env)
    spec = application_spec(ROOT)
    if args.operation == 'plan':
        print(json.dumps(spec, indent=2))
        return
    training_python = ROOT / '.venv-router-train/bin/python'
    subprocess.run([str(training_python), '-c', 'import tensorboard; print(tensorboard.__version__)'],
                   env=isolated_environment(ROOT, training_python), check=True)
    from cai_integration.cml_env import resolve_cml_connection
    from ray_serve_cai.cai_cluster import CMLAPIClient
    connection = resolve_cml_connection()
    if not all((connection.host, connection.api_key, connection.project_id)):
        raise RuntimeError('Run inside the CAI project with its injected API credentials')
    client = CMLAPIClient(connection.host, connection.api_key)
    app = ensure_application(client, connection.project_id, spec)
    record = {'id': app.id, 'status': app.status, 'subdomain': app.subdomain,
              'logdir': str(ROOT / 'training-runs')}
    if os.environ.get('CDSW_DOMAIN'):
        record['url'] = f"https://{app.subdomain}.{os.environ['CDSW_DOMAIN']}"
    state = ROOT / '.amp-state'
    state.mkdir(exist_ok=True)
    (state / 'tensorboard-application.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    print('Application recorded; check CAI Applications for readiness. Existing apps are not restarted.')


if __name__ == '__main__':
    main()
