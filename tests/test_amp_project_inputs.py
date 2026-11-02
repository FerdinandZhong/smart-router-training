import io
import json
import os
import unittest
from unittest.mock import patch

from cai_integration.project_environment import (
    SUBDOMAIN_INPUTS, validate_project_environment, preflight_project_environment,
)
from cai_integration.create_amp import build_payload


class ProjectInputTests(unittest.TestCase):
    def test_custom_strings_preserved(self):
        expected = {key: "customer-" + str(i) for i, key in enumerate(SUBDOMAIN_INPUTS)}
        self.assertEqual(validate_project_environment(json.dumps(expected)), expected)

    def test_browser_event_has_actionable_error(self):
        event = dict.fromkeys(["dispatchConfig", "nativeEvent", "target", "_targetInst"])
        with self.assertRaisesRegex(ValueError, "Re-enter the intended values"):
            validate_project_environment({SUBDOMAIN_INPUTS[0]: event})

    def test_serialized_event_is_not_a_valid_subdomain(self):
        with self.assertRaisesRegex(ValueError, "DNS label"):
            validate_project_environment({SUBDOMAIN_INPUTS[0]: '{"target": null}'})

    def test_other_non_string_values_still_fail(self):
        with self.assertRaisesRegex(ValueError, "non-string"):
            validate_project_environment({"OTHER": {"default": "value"}})

    def test_repaired_api_values_replace_stale_process_names_only(self):
        stored = {key: "customer-" + str(i) for i, key in enumerate(SUBDOMAIN_INPUTS)}
        stored["UNRELATED"] = "stored-value"
        response = io.BytesIO(json.dumps({"environment": json.dumps(stored)}).encode())
        env = {"CML_HOST": "https://example.invalid", "CDSW_PROJECT_ID": "project",
               "CDSW_APIV2_KEY": "test-credential", "UNRELATED": "keep-process-value",
               **{key: "[object Object]" for key in SUBDOMAIN_INPUTS}}
        with patch.dict(os.environ, env, clear=True), patch(
            "cai_integration.project_environment.urlopen", return_value=response
        ) as request:
            preflight_project_environment()
            for key in SUBDOMAIN_INPUTS:
                self.assertEqual(os.environ[key], stored[key])
            self.assertEqual(os.environ["UNRELATED"], "keep-process-value")
            self.assertEqual(request.call_args.args[0].get_method(), "GET")
            request.assert_called_once()

    def test_invalid_api_does_not_change_process(self):
        raw = {SUBDOMAIN_INPUTS[0]: "correct-name", SUBDOMAIN_INPUTS[1]: {}}
        response = io.BytesIO(json.dumps({"environment": json.dumps(raw)}).encode())
        with patch.dict(os.environ, {"CML_HOST":"https://example.invalid", "CDSW_PROJECT_ID":"p",
                                   "CDSW_APIV2_KEY":"test", SUBDOMAIN_INPUTS[0]:"keep"}), patch(
            "cai_integration.project_environment.urlopen", return_value=response
        ):
            with self.assertRaises(ValueError):
                preflight_project_environment()
            self.assertEqual(os.environ[SUBDOMAIN_INPUTS[0]], "keep")

    def test_api_import_keeps_custom_inputs_not_definitions(self):
        definitions = {key:{"default":"default-name"} for key in SUBDOMAIN_INPUTS}
        custom = {key:"custom-"+str(i) for i,key in enumerate(SUBDOMAIN_INPUTS)}
        payload = build_payload({"description":"test", "environment_variables":definitions}, custom,
                                name="test", runtime="runtime", git_url="https://example.invalid/repo", git_ref="training-demo")
        self.assertEqual(payload["create_project_request"]["environment"], custom)

if __name__ == "__main__":
    unittest.main()
