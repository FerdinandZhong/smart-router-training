"""CAI application safety, idempotency and PBJ execution contracts."""
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from amp.tensorboard_app import application_spec, ensure_application, serve

ROOT = Path(__file__).resolve().parents[1]


class TensorBoardAppTests(unittest.TestCase):
    def test_application_is_cpu_only_and_authenticated(self):
        spec = application_spec(ROOT, {'CDSW_APIV2_KEY': 'not-forwarded'})
        self.assertEqual(spec['num_gpus'], 0)
        self.assertFalse(spec['bypass_authentication'])
        self.assertNotIn('environment', spec)
        self.assertTrue((ROOT / spec['script']).is_file())
        with self.assertRaises(ValueError):
            application_spec(ROOT, {'TENSORBOARD_SUBDOMAIN': 'https://wrong'})

    def test_repeat_deployment_reuses_app_and_rejects_unsafe_collision(self):
        spec = application_spec(ROOT, {})
        client = Mock()
        app = SimpleNamespace(subdomain=spec['subdomain'], metadata={
            'script': spec['script'], 'bypass_authentication': False})
        client.list_applications.return_value = [app]
        self.assertIs(ensure_application(client, 'project', spec), app)
        client.create_application.assert_not_called()
        app.metadata['bypass_authentication'] = True
        with self.assertRaises(RuntimeError):
            ensure_application(client, 'project', spec)
        client.create_application.assert_not_called()

    def test_create_uses_current_project(self):
        client = Mock()
        client.list_applications.return_value = []
        spec = application_spec(ROOT, {})
        ensure_application(client, 'project', spec)
        client.create_application.assert_called_once_with(project_id='project', **spec)

    def test_server_uses_app_port_shared_storage_and_isolated_python(self):
        with patch.dict(os.environ, {'CDSW_APP_PORT': '8123', 'PYTHONPATH': '/runtime-addons',
                                    'PYTHONHOME': '/bad'}), \
             patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'mkdir'), patch('subprocess.run') as run:
            serve(ROOT)
        command = run.call_args.args[0]
        self.assertIn('8123', command)
        self.assertIn(str(ROOT / 'training-runs'), command)
        self.assertIn('tensorboard.main', command)
        self.assertNotIn('PYTHONHOME', run.call_args.kwargs['env'])
        self.assertNotIn('/runtime-addons', run.call_args.kwargs['env']['PYTHONPATH'])

    def test_application_wrapper_handles_notebook_kernel_arguments(self):
        import sys
        source = ROOT / 'amp/serve_tensorboard.py'
        with patch.dict(os.environ, {'CDSW_PROJECT_DIR': str(ROOT)}), \
             patch.object(sys, 'argv', ['ipykernel_launcher.py', '-f', '/tmp/kernel.json']), \
             patch.object(sys, 'path', list(sys.path)), patch('subprocess.run') as run:
            exec(compile(source.read_text(), '<CAI-cell>', 'exec'), {'__name__': '__main__'})
        self.assertEqual(run.call_args.args[0][-2:], [str(ROOT / 'amp/tensorboard_app.py'), 'serve'])
