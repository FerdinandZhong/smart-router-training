"""Serve real TensorBoard through the application launcher and query its scalars."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from urllib.parse import urlencode
from torch.utils.tensorboard import SummaryWriter

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / '.venv-router-train').symlink_to(sys.prefix, target_is_directory=True)
        events = root / 'training-runs/test-run/tensorboard/initial'
        with SummaryWriter(str(events)) as writer:
            writer.add_scalar('diagnostic/loss', 2.5, 1)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = {**os.environ, 'CDSW_APP_PORT': str(port), 'PYTHONPATH': str(ROOT)}
        code = 'from pathlib import Path; from amp.tensorboard_app import serve; import sys; serve(Path(sys.argv[1]))'
        with (root / 'server.log').open('w+') as log:
            process = subprocess.Popen([sys.executable, '-c', code, str(root)], env=env,
                                       stdout=log, stderr=log, start_new_session=True)
            try:
                endpoint = f'http://127.0.0.1:{port}'
                deadline = time.monotonic() + 45
                runs = []
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        log.seek(0)
                        raise AssertionError(log.read())
                    try:
                        with urlopen(endpoint + '/data/runs', timeout=2) as response:
                            runs = json.load(response)
                        if runs:
                            break
                    except OSError:
                        pass
                    time.sleep(0.5)
                assert runs, 'TensorBoard did not discover events'
                query = urlencode({'run': runs[0], 'tag': 'diagnostic/loss'})
                with urlopen(endpoint + '/data/plugin/scalars/scalars?' + query, timeout=5) as response:
                    points = json.load(response)
                assert points[0][1:] == [1, 2.5], points
                with urlopen(endpoint + '/', timeout=5) as response:
                    assert response.status == 200
                print('PASS: actual TensorBoard HTTP UI, shared event discovery and scalar API')
            finally:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
