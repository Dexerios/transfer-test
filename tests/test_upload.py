import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import requests


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
TEST_ENV = {
    "ROBLOX_API_KEY": "test-api-key",
    "TRANSFER_UPLOAD_SECRET": "test-current-secret",
    "TRANSFER_UPLOAD_SECRET_PREVIOUS": "test-previous-secret",
}


def load_app(environment):
    spec = importlib.util.spec_from_file_location("transfer_test_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, environment, clear=True):
        spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.module = load_app(TEST_ENV)
        self.client = self.module.app.test_client()
        self.headers = {"X-Transfer-Secret": TEST_ENV["TRANSFER_UPLOAD_SECRET"]}
        self.payload = {"entryKey": "Player_123", "data": {"1": {"Level": 42}}}
        self.writer = patch.object(self.module, "write_to_datastore")
        self.write = self.writer.start()
        self.addCleanup(self.writer.stop)

    def test_health_does_not_write(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"OK")
        self.write.assert_not_called()

    def test_current_secret_preserves_transfer_format(self):
        response = self.client.post("/upload", json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True, "writtenKey": "Player_123"})
        self.write.assert_called_once_with("Player_123", json.dumps(self.payload["data"]))

    def test_list_slots_are_preserved(self):
        self.payload["data"] = [{"Level": 42}, {"Level": 7}]
        response = self.client.post("/upload", json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.write.assert_called_once_with("Player_123", json.dumps(self.payload["data"]))

    def test_previous_secret_works_during_rotation(self):
        response = self.client.post("/upload", json=self.payload, headers={
            "X-Transfer-Secret": TEST_ENV["TRANSFER_UPLOAD_SECRET_PREVIOUS"]
        })
        self.assertEqual(response.status_code, 200)

    def test_missing_wrong_and_empty_secrets_never_write(self):
        for headers in [{}, {"X-Transfer-Secret": ""}, {"X-Transfer-Secret": "wrong"}]:
            with self.subTest(headers=headers):
                response = self.client.post("/upload", json=self.payload, headers=headers)
                self.assertEqual(response.status_code, 401)
        self.write.assert_not_called()

    def test_removing_previous_secret_retires_it(self):
        environment = dict(TEST_ENV)
        environment.pop("TRANSFER_UPLOAD_SECRET_PREVIOUS")
        module = load_app(environment)
        with patch.object(module, "write_to_datastore") as write:
            client = module.app.test_client()
            response = client.post("/upload", json=self.payload, headers={
                "X-Transfer-Secret": TEST_ENV["TRANSFER_UPLOAD_SECRET_PREVIOUS"]
            })
            self.assertEqual(response.status_code, 401)
            response = client.post("/upload", json=self.payload, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            write.assert_called_once()

    def test_startup_requires_both_credentials(self):
        for key in ["ROBLOX_API_KEY", "TRANSFER_UPLOAD_SECRET"]:
            for value in [None, ""]:
                environment = dict(TEST_ENV)
                if value is None:
                    environment.pop(key)
                else:
                    environment[key] = value
                with self.subTest(key=key, value=value):
                    with self.assertRaisesRegex(RuntimeError, key):
                        load_app(environment)

    def test_invalid_payloads_never_write(self):
        payloads = [None, [], "text", {}, {"entryKey": "Player_123", "data": "bad"}]
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post("/upload", data=json.dumps(payload),
                                            content_type="application/json", headers=self.headers)
                self.assertEqual(response.status_code, 400)
        self.write.assert_not_called()

    def test_invalid_keys_including_trailing_newline_never_write(self):
        for key in ["Player_0", "Player_-1", "Player_1\n", "Other_1", "Player_" + "9" * 21]:
            self.payload["entryKey"] = key
            with self.subTest(key=key):
                response = self.client.post("/upload", json=self.payload, headers=self.headers)
                self.assertEqual(response.status_code, 400)
        self.write.assert_not_called()

    def test_malformed_json_never_writes(self):
        response = self.client.post("/upload", data="{", headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.write.assert_not_called()

    def test_authentication_runs_before_json_parsing(self):
        with patch.object(self.module, "request", Mock(headers={})) as request:
            response = self.client.post("/upload", data="{", headers={})
            request.get_json.assert_not_called()
        self.assertEqual(response.status_code, 401)
        self.write.assert_not_called()

    def test_request_limit_returns_json_413_without_writing(self):
        response = self.client.post("/upload", data=b" " * 4_194_305, headers=self.headers)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json["success"], False)
        self.write.assert_not_called()

    def test_request_limit_also_covers_stream_without_content_length(self):
        stream = io.BytesIO(b" " * 4_194_305)
        response = self.client.open("/upload", method="POST", headers=self.headers,
                                    environ_overrides={
                                        "CONTENT_LENGTH": "",
                                        "wsgi.input_terminated": True,
                                        "wsgi.input": stream,
                                    })
        self.assertIn(response.status_code, (400, 413))
        self.assertLessEqual(stream.tell(), 4_194_304)
        self.assertGreater(stream.tell(), 0)
        self.write.assert_not_called()

    def test_entry_limit_still_applies(self):
        self.payload["data"] = {"1": "x" * 3_500_001}
        response = self.client.post("/upload", json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 413)
        self.write.assert_not_called()

    def test_large_valid_entry_still_transfers(self):
        self.payload["data"] = {"1": "x" * 3_400_000}
        response = self.client.post("/upload", json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.write.assert_called_once()

    def test_upstream_errors_do_not_leak_internal_details(self):
        for error in [requests.HTTPError("private upstream details"), requests.Timeout("private timeout")]:
            self.write.side_effect = error
            response = self.client.post("/upload", json=self.payload, headers=self.headers)
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json, {"success": False, "error": "Roblox API error"})

    def test_internal_errors_do_not_leak_details(self):
        self.write.side_effect = RuntimeError("private internal details")
        response = self.client.post("/upload", json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {"success": False, "error": "upload failed"})


class DatastoreTests(unittest.TestCase):
    def setUp(self):
        self.module = load_app(TEST_ENV)

    def test_writer_keeps_destination_key_body_and_auth_contract(self):
        with patch.object(self.module.requests, "post", return_value=Mock(status_code=200)) as post:
            self.module.write_to_datastore("Player_123", '{"1": {"Level": 42}}')
        args, kwargs = post.call_args
        self.assertIn("/universes/3064619271/", args[0])
        self.assertEqual(kwargs["params"], {
            "datastoreName": "TransferStore", "scope": "global", "entryKey": "Player_123"
        })
        self.assertEqual(kwargs["headers"]["x-api-key"], TEST_ENV["ROBLOX_API_KEY"])
        self.assertEqual(kwargs["data"], '{"1": {"Level": 42}}')
        self.assertEqual(kwargs["timeout"], 10)

    def test_rate_limits_and_outages_still_retry(self):
        responses = [Mock(status_code=429), Mock(status_code=503), Mock(status_code=200)]
        with patch.object(self.module.requests, "post", side_effect=responses) as post:
            with patch.object(self.module.time, "sleep") as sleep:
                self.module.write_to_datastore("Player_123", "[]")
        self.assertEqual(post.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])


if __name__ == "__main__":
    unittest.main()
