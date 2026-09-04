import base64
import contextlib
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests
import cli
import example

TOKEN = "test-editor-token-" + "x" * 32
RAW = b"original-" * 8
EDITED = b"edited!!" * 9


def response(data, status=200):
    result = Mock(status_code=status)
    result.json.return_value = data
    return result


def save_response():
    return {"success": True, "save_base64": base64.b64encode(EDITED).decode(), "sha256": hashlib.sha256(EDITED).hexdigest(), "change_count": 1}


class CLITests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.source = self.folder / "original.save"
        self.source.write_bytes(RAW)
        self.ops = self.folder / "operations.json"
        self.ops.write_text(json.dumps([{"action": "items.xp", "args": {"value": 1000}}]))
        self.target = self.folder / "new.save"
        self.stack.enter_context(patch.dict(os.environ, {"EDITOR_API_KEY": TOKEN, "TEMPLATE_API_KEY": ""}))
        self.session = Mock()
        self.session.request.return_value = response(save_response())
        self.stack.enter_context(patch.object(cli.requests, "Session", return_value=self.session))
        self.stdout = StringIO()
        self.stderr = StringIO()
        self.stack.enter_context(contextlib.redirect_stdout(self.stdout))
        self.stack.enter_context(contextlib.redirect_stderr(self.stderr))

    def test_edit_uses_bearer_v2_file_payload_and_preserves_input(self):
        code = cli.main(["edit", str(self.source), str(self.ops), str(self.target)])
        self.assertEqual(code, 0)
        args, kwargs = self.session.request.call_args
        self.assertEqual(args, ("POST", cli.DEFAULT_URL + "/v2/save/edit"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer " + TOKEN)
        self.assertEqual(base64.b64decode(kwargs["json"]["save_base64"]), RAW)
        self.assertEqual(kwargs["json"]["operations"][0]["action"], "items.xp")
        self.assertNotIn("transfer_code", kwargs["json"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(self.source.read_bytes(), RAW)
        self.assertEqual(self.target.read_bytes(), EDITED)
        self.assertNotIn(TOKEN, self.stdout.getvalue() + self.stderr.getvalue())

    def test_missing_auth_fails_before_http(self):
        with patch.dict(os.environ, {"EDITOR_API_KEY": "", "TEMPLATE_API_KEY": ""}):
            self.assertEqual(cli.main(["inspect", str(self.source)]), 1)
        self.session.request.assert_not_called()

    def test_features_is_public_without_token(self):
        self.session.request.return_value = response({"success": True, "actions": {}})
        with patch.dict(os.environ, {"EDITOR_API_KEY": "", "TEMPLATE_API_KEY": ""}):
            self.assertEqual(cli.main(["features"]), 0)
        self.assertNotIn("Authorization", self.session.request.call_args.kwargs["headers"])

    def test_template_key_fallback_and_explicit_token(self):
        with patch.dict(os.environ, {"EDITOR_API_KEY": "", "TEMPLATE_API_KEY": TOKEN}):
            client = cli.EditorClient()
            client.inspect(RAW)
        self.assertEqual(self.session.request.call_args.kwargs["headers"]["Authorization"], "Bearer " + TOKEN)
        client = cli.EditorClient(token="explicit")
        client.inspect(RAW)
        self.assertEqual(self.session.request.call_args.kwargs["headers"]["Authorization"], "Bearer explicit")

    def test_input_alias_or_existing_output_fails_before_http(self):
        for target in (self.source, self.folder / "existing.save"):
            target.write_bytes(RAW)
            with self.subTest(target=target):
                code = cli.main(["edit", str(self.source), str(self.ops), str(target)])
                self.assertEqual(code, 1)
                self.assertEqual(target.read_bytes(), RAW)
        self.session.request.assert_not_called()

    def test_http_error_does_not_create_output_or_print_token(self):
        self.session.request.return_value = response({"success": False, "message": "Rejected " + TOKEN}, 422)
        self.assertEqual(cli.main(["edit", str(self.source), str(self.ops), str(self.target)]), 1)
        self.assertFalse(self.target.exists())
        self.assertIn("HTTP 422", self.stderr.getvalue())
        self.assertNotIn(TOKEN, self.stderr.getvalue())
        self.assertEqual(self.source.read_bytes(), RAW)

    def test_network_exception_is_sanitized_and_not_retried(self):
        self.session.request.side_effect = requests.RequestException("secret=" + TOKEN)
        self.assertEqual(cli.main(["inspect", str(self.source)]), 1)
        self.assertEqual(self.session.request.call_count, 1)
        self.assertNotIn(TOKEN, self.stderr.getvalue())

    def test_malformed_or_mismatched_save_response_creates_no_file(self):
        for result in ({"success": True, "save_base64": "bad!"}, {**save_response(), "sha256": "wrong"}, {"success": False}):
            self.session.request.return_value = response(result)
            with self.subTest(result=result):
                self.assertEqual(cli.main(["edit", str(self.source), str(self.ops), str(self.target)]), 1)
                self.assertFalse(self.target.exists())

    def test_inspect_prints_only_metadata_and_not_account_state(self):
        self.session.request.return_value = response({"success": True, "bytes": len(RAW), "country_code": "kr", "state": {"password_refresh_token": "sensitive-game-auth"}})
        self.assertEqual(cli.main(["inspect", str(self.source)]), 0)
        output = json.loads(self.stdout.getvalue())
        self.assertEqual(output["bytes"], len(RAW))
        self.assertNotIn("state", output)
        self.assertNotIn("sensitive-game-auth", self.stdout.getvalue())

    def test_export_and_import_preserve_files_and_send_only_state(self):
        state = {"cc": "kr", "game_version": 150500, "xp": 123}
        self.session.request.return_value = response({"success": True, "state": state})
        exported = self.folder / "state.json"
        self.assertEqual(cli.main(["export", str(self.source), str(exported)]), 0)
        self.assertEqual(json.loads(exported.read_text())["state"], state)
        self.session.request.return_value = response(save_response())
        self.assertEqual(cli.main(["import", str(exported), str(self.target)]), 0)
        self.assertEqual(self.session.request.call_args.kwargs["json"], {"state": state})
        self.assertEqual(self.target.read_bytes(), EDITED)
        self.assertEqual(self.source.read_bytes(), RAW)

    def test_python_example_has_authenticated_file_edit_only(self):
        self.assertEqual(example.main([str(self.source), str(self.target)]), 0)
        args, kwargs = self.session.request.call_args
        self.assertTrue(args[1].endswith("/v2/save/edit"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer " + TOKEN)
        self.assertEqual(self.source.read_bytes(), RAW)
        self.assertEqual(self.target.read_bytes(), EDITED)
        self.assertNotIn(TOKEN, self.stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
