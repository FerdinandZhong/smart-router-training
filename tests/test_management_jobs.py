"""Management Ray Jobs facade contracts; no cluster mutation."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ray_serve_cai.management.api import jobs
from ray_serve_cai.management.auth import require_admin, require_user


class ManagementJobsTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        from fastapi import Depends
        self.app.include_router(jobs.router, dependencies=[Depends(require_user)])
        self.client = TestClient(self.app)
        self.body = {"submission_id": "smoke-001", "entrypoint": "python train.py",
                     "runtime_env": {"py_executable": "/home/cdsw/.venv-router-train/bin/python"}}

    def allow(self):
        self.app.dependency_overrides[require_user] = lambda: object()
        self.app.dependency_overrides[require_admin] = lambda: object()

    def test_auth_required_before_submission(self):
        with patch.object(jobs, 'dashboard_request') as forward:
            self.assertEqual(self.client.post('/api/v1/jobs', json=self.body).status_code, 401)
            forward.assert_not_called()

    def test_authenticated_reader_cannot_submit(self):
        from fastapi import HTTPException
        self.app.dependency_overrides[require_user] = lambda: object()
        def deny():
            raise HTTPException(403, 'Admin role required')
        self.app.dependency_overrides[require_admin] = deny
        with patch.object(jobs, 'dashboard_request') as forward:
            self.assertEqual(self.client.post('/api/v1/jobs', json=self.body).status_code, 403)
            forward.assert_not_called()

    def test_submit_and_swagger(self):
        self.allow()
        with patch.object(jobs, 'dashboard_request', return_value={'submission_id': 'smoke-001'}) as forward:
            response = self.client.post('/api/v1/jobs', json=self.body)
            self.assertEqual(response.status_code, 201)
            payload = forward.call_args.args[2]
            self.assertEqual(payload['runtime_env'], self.body['runtime_env'])
            self.assertEqual(payload['entrypoint_num_gpus'], 0)
        schema = self.app.openapi()
        self.assertIn('/api/v1/jobs', schema['paths'])
        self.assertIn('example', schema['components']['schemas']['SubmitJobRequest'])

    def test_validation(self):
        self.allow()
        with patch.object(jobs, 'dashboard_request') as forward:
            for extra in ({'name': 'wrong-api'}, {'entrypoint_num_gpus': -1}, {'submission_id': '../bad'}):
                self.assertEqual(self.client.post('/api/v1/jobs', json={**self.body, **extra}).status_code, 422)
            forward.assert_not_called()

    def test_status_logs_and_stop(self):
        self.allow()
        for suffix, method, tail in [('', 'GET', ''), ('/smoke-001', 'GET', 'smoke-001'),
                                     ('/smoke-001/logs', 'GET', 'smoke-001/logs'),
                                     ('/smoke-001/stop', 'POST', 'smoke-001/stop')]:
            with patch.object(jobs, 'dashboard_request', return_value={}) as forward:
                self.assertEqual(self.client.request(method, '/api/v1/jobs' + suffix).status_code, 200)
                self.assertEqual(forward.call_args.args[0], tail)

    def test_forward_to_local_dashboard_without_auth(self):
        response = io.BytesIO(json.dumps({'submission_id': 'smoke-001'}).encode())
        with patch.object(jobs, 'urlopen', return_value=response) as open_url:
            self.assertEqual(jobs.dashboard_request('', 'POST', self.body)['submission_id'], 'smoke-001')
            request = open_url.call_args.args[0]
            self.assertEqual(request.full_url, 'http://127.0.0.1:8265/api/jobs/')
            self.assertFalse(request.has_header('Authorization'))
            self.assertEqual(json.loads(request.data), self.body)

    def test_dashboard_errors(self):
        for error, expected in [(HTTPError('local', 404, 'missing', {}, io.BytesIO(b'missing')), 404),
                                (HTTPError('local', 500, 'internal', {}, io.BytesIO(b'secret')), 502),
                                (URLError('connection refused'), 502)]:
            with patch.object(jobs, 'urlopen', side_effect=error):
                from fastapi import HTTPException
                with self.assertRaises(HTTPException) as raised:
                    jobs.dashboard_request('missing')
                self.assertEqual(raised.exception.status_code, expected)
                self.assertNotIn('secret', raised.exception.detail)
