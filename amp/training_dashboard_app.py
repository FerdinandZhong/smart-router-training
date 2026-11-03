"""Provision or serve the authenticated training dashboard CAI application."""
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
from amp.tensorboard_app import ensure_application


def application_spec(root, environment=None):
    env = os.environ if environment is None else environment
    subdomain = env.get('TRAINING_DASHBOARD_SUBDOMAIN', 'model-training-dashboard')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', subdomain):
        raise ValueError('TRAINING_DASHBOARD_SUBDOMAIN must be a DNS label')
    import yaml
    config = yaml.safe_load((root / 'configs/ray_cluster_config.yaml').read_text())
    return dict(name='Smart Router Training Dashboard', script='amp/serve_training_dashboard.py',
                cpu=2, memory=4, num_gpus=0,
                runtime_identifier=config['cai']['head_runtime_identifier'],
                subdomain=subdomain, bypass_authentication=False)


def serve(root=ROOT):
    python = root / '.venv-router-train/bin/python'
    if not python.exists():
        raise RuntimeError('Run amp/setup_training_environment.py first')
    port = int(os.environ['CDSW_APP_PORT'])
    if not 1 <= port <= 65535:
        raise ValueError('Invalid CDSW_APP_PORT')
    # The monitor binds 127.0.0.1 only; CAI ingress supplies authentication and TLS.
    command = [str(python), str(root / 'amp/training_demo/monitor.py'), '--port', str(port)]
    print(f'Serving training dashboard on port {port}', flush=True)
    state = root / '.amp-state'
    state.mkdir(exist_ok=True)
    with (state / 'training-dashboard-server.log').open('a', buffering=1) as log:
        with subprocess.Popen(command, cwd=root, env=isolated_environment(root, python),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
            for line in process.stdout:
                log.write(line)
                print(line, end='', flush=True)
            returncode = process.wait()
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['plan', 'deploy'])
    args = parser.parse_args()
    python = ROOT / '.venv/bin/python'
    if args.operation == 'deploy':
        if not python.exists():
            raise RuntimeError('Run amp/setup_cluster_environment.py first')
        env = isolated_environment(ROOT, python)
        if Path(sys.prefix).resolve() != python.parent.parent.resolve() or any(
            os.environ.get(k) != env.get(k) for k in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONNOUSERSITE')
        ):
            os.execve(str(python), [str(python), str(ROOT / 'amp/training_dashboard_app.py'), 'deploy'], env)
    spec = application_spec(ROOT)
    if args.operation == 'plan':
        print(json.dumps(spec, indent=2))
        return
    from cai_integration.cml_env import resolve_cml_connection
    from ray_serve_cai.cai_cluster import CMLAPIClient
    connection = resolve_cml_connection()
    if not all((connection.host, connection.api_key, connection.project_id)):
        raise RuntimeError('Run inside the CAI project with its injected API credentials')
    client = CMLAPIClient(connection.host, connection.api_key)
    app = ensure_application(client, connection.project_id, spec)
    record = {'id': app.id, 'status': app.status, 'subdomain': app.subdomain}
    if os.environ.get('CDSW_DOMAIN'):
        record['url'] = f"https://{app.subdomain}.{os.environ['CDSW_DOMAIN']}"
    state = ROOT / '.amp-state'
    state.mkdir(exist_ok=True)
    (state / 'training-dashboard-application.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    print('Application recorded; check CAI Applications for readiness. Existing apps are not restarted.')


if __name__ == '__main__':
    main()
