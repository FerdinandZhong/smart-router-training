"""Reproduce CAI add-on metadata leaking into an otherwise isolated venv."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from amp.environment import isolated_environment


class EnvironmentIsolationTests(unittest.TestCase):
    def test_preserves_platform_and_gpu_settings_without_python_injection(self):
        base = {"PYTHONPATH": "/runtime-addons/python/site-packages",
                "PYTHONHOME": "/runtime", "PATH": "/usr/bin",
                "CDSW_APIV2_KEY": "test-only", "CUDA_HOME": "/usr/local/cuda",
                "LD_LIBRARY_PATH": "/cuda/lib64", "NCCL_SOCKET_IFNAME": "eth0"}
        env = isolated_environment(Path('/project'), Path('/project/.venv/bin/python'), base)
        self.assertNotIn('PYTHONHOME', env)
        self.assertNotIn('/runtime-addons', env['PYTHONPATH'])
        for key in ('CDSW_APIV2_KEY', 'CUDA_HOME', 'LD_LIBRARY_PATH', 'NCCL_SOCKET_IFNAME'):
            self.assertEqual(env[key], base[key])
        self.assertIn('PYTHONHOME', base)
        self.assertEqual(isolated_environment('/project', '/project/.venv/bin/python', env), env)

    def test_real_venv_pip_check_excludes_injected_addon(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / '.venv/bin/python'
            clean = isolated_environment(root, python)
            subprocess.run([sys.executable, '-m', 'venv', str(python.parent.parent)],
                           env=clean, check=True, capture_output=True)
            addon = root / 'runtime-addons'
            metadata = addon / 'fake_cai_plugin-1.0.dist-info'
            metadata.mkdir(parents=True)
            (metadata / 'METADATA').write_text(
                'Metadata-Version: 2.1\nName: fake-cai-plugin\nVersion: 1.0\n'
                'Requires-Dist: missing-cai-dependency==1.0\n')
            (addon / 'cai_addon_probe.py').write_text('INJECTED = True\n')
            contaminated = {**clean, 'PYTHONPATH': str(addon)}
            before = subprocess.run([str(python), '-m', 'pip', 'check'],
                                    env=contaminated, capture_output=True, text=True)
            self.assertNotEqual(before.returncode, 0)
            self.assertIn('fake-cai-plugin', before.stdout)
            repaired = isolated_environment(root, python, contaminated)
            after = subprocess.run([str(python), '-m', 'pip', 'check'],
                                   env=repaired, capture_output=True, text=True)
            self.assertEqual(after.returncode, 0, after.stdout + after.stderr)
            probe = subprocess.check_output([str(python), '-c',
                'import importlib.util,json,sys; print(json.dumps({'
                '"addon": importlib.util.find_spec("cai_addon_probe") is not None,'
                '"prefix": sys.prefix}))'], env=repaired, text=True)
            result = json.loads(probe)
            self.assertFalse(result['addon'])
            self.assertEqual(Path(result['prefix']), python.parent.parent)


if __name__ == '__main__':
    unittest.main()
