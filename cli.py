"""File-based v2 API client. Never receives or uploads game transfer codes.

Examples:
  python cli.py features
  python cli.py inspect original.save --country kr
  python cli.py edit original.save operations.json edited.save --country kr
  python cli.py export original.save state.json --country kr
  python cli.py import state.json restored.save

Set EDITOR_API_KEY (or TEMPLATE_API_KEY) in the environment. --token is also
accepted. Existing files are never overwritten; choose a new output filename.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

import requests

DEFAULT_URL = "http://127.0.0.1:5000"
MAX_SAVE_BYTES = 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024


class ClientError(ValueError):
    pass


class EditorClient:
    def __init__(self, url=DEFAULT_URL, token=None, session=None):
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ClientError("Use the API origin as --url, for example http://127.0.0.1:5000")
        self.url = url.rstrip("/")
        self.token = token or os.environ.get("EDITOR_API_KEY") or os.environ.get("TEMPLATE_API_KEY")
        self.session = session or requests.Session()

    def redact(self, value):
        text = str(value)
        return text.replace(self.token, "[redacted]") if self.token else text

    def request(self, method, path, payload=None, auth=True):
        if auth and not self.token:
            raise ClientError("Set EDITOR_API_KEY or TEMPLATE_API_KEY, or pass --token")
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            response = self.session.request(method, self.url + path, json=payload, headers=headers,
                                            timeout=(5, 60), allow_redirects=False)
        except requests.RequestException:
            raise ClientError("The API request could not be completed") from None
        if not 200 <= response.status_code < 300:
            message = "API request failed"
            try:
                detail = response.json()
                if isinstance(detail, dict) and isinstance(detail.get("message"), str):
                    message = self.redact(detail["message"])[:500]
            except ValueError:
                message = "The server did not return a JSON error"
            raise ClientError(f"HTTP {response.status_code}: {message}")
        try:
            result = response.json()
        except ValueError:
            raise ClientError("The API returned invalid JSON") from None
        if not isinstance(result, dict) or result.get("success") is not True:
            raise ClientError("The API did not confirm success")
        return result

    def features(self):
        return self.request("GET", "/v2/features", auth=False)

    def inspect(self, raw, country="kr"):
        return self.request("POST", "/v2/save/inspect", save_payload(raw, country))

    def edit(self, raw, operations, country="kr"):
        if not isinstance(operations, list) or not operations:
            raise ClientError("operations.json must contain a nonempty operations array")
        return self.request("POST", "/v2/save/edit", {**save_payload(raw, country), "operations": operations})

    def export(self, raw, country="kr"):
        return self.request("POST", "/v2/save/export", save_payload(raw, country))

    def import_state(self, state):
        if not isinstance(state, dict):
            raise ClientError("The exported state must be a JSON object")
        return self.request("POST", "/v2/save/import", {"state": state})


def save_payload(raw, country):
    if not isinstance(raw, bytes) or not 32 <= len(raw) <= MAX_SAVE_BYTES:
        raise ClientError("Save files must contain 32 bytes to 1 MiB")
    if country not in ("kr", "en", "jp", "tw"):
        raise ClientError("country must be kr, en, jp or tw")
    return {"save_base64": base64.b64encode(raw).decode("ascii"), "country_code": country}


def save_bytes(result):
    encoded = result.get("save_base64")
    if not isinstance(encoded, str) or len(encoded) > ((MAX_SAVE_BYTES + 2) // 3) * 4:
        raise ClientError("The API response has no valid save payload")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ClientError("The API returned invalid save_base64") from None
    if not 32 <= len(raw) <= MAX_SAVE_BYTES:
        raise ClientError("The API returned an unsupported save size")
    digest = result.get("sha256")
    if digest is not None and digest != hashlib.sha256(raw).hexdigest():
        raise ClientError("The downloaded save checksum does not match the API response")
    return raw


def read_file(path, maximum=MAX_SAVE_BYTES):
    try:
        with Path(path).open("rb") as handle:
            value = handle.read(maximum + 1)
    except OSError:
        raise ClientError("An input file could not be read") from None
    if len(value) > maximum:
        raise ClientError("An input file exceeds its size limit")
    return value


def read_json(path):
    try:
        return json.loads(read_file(path, MAX_JSON_BYTES).decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        raise ClientError("An input file is not valid JSON") from None


def output_path(path, inputs=()):
    target = Path(path).resolve()
    if any(target == Path(item).resolve() for item in inputs):
        raise ClientError("The output path must be different from every input file")
    if target.exists():
        raise ClientError("The output already exists; choose a new filename")
    return target


def write_new(path, data):
    """Exclusive creation also protects against another process creating output."""
    target = Path(path).resolve()
    created = False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            created = True
            handle.write(data)
    except OSError:
        if created:
            target.unlink(missing_ok=True)
        raise ClientError("Output could not be written without overwriting an existing file") from None


def parser():
    value = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    value.add_argument("--url", default=DEFAULT_URL, help="API origin (default: http://127.0.0.1:5000)")
    value.add_argument("--token", default=None, help="API bearer key; defaults to EDITOR_API_KEY/TEMPLATE_API_KEY")
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("features", help="Show action schemas and feature coverage")
    inspect = commands.add_parser("inspect", help="Show file metadata without printing account state")
    inspect.add_argument("input")
    inspect.add_argument("--country", choices=("kr", "en", "jp", "tw"), default="kr")
    for name in ("edit", "export"):
        command = commands.add_parser(name)
        command.add_argument("input")
        if name == "edit":
            command.add_argument("operations", help="JSON array of {action, args} objects")
        command.add_argument("output")
        command.add_argument("--country", choices=("kr", "en", "jp", "tw"), default="kr")
    restore = commands.add_parser("import", help="Import a state object or a complete export response")
    restore.add_argument("input")
    restore.add_argument("output")
    return value


def main(argv=None):
    args = parser().parse_args(argv)
    client = None
    try:
        client = EditorClient(args.url, args.token)
        if args.command == "features":
            report = client.features()
        elif args.command == "inspect":
            result = client.inspect(read_file(args.input), args.country)
            report = {key: result[key] for key in ("success", "country_code", "game_version", "bytes", "sha256") if key in result}
        else:
            inputs = [args.input] + ([args.operations] if args.command == "edit" else [])
            target = output_path(args.output, inputs)
            if args.command == "edit":
                operations = read_json(args.operations)
                if isinstance(operations, dict) and set(operations) == {"operations"}:
                    operations = operations["operations"]
                result = client.edit(read_file(args.input), operations, args.country)
                content = save_bytes(result)
            elif args.command == "export":
                result = client.export(read_file(args.input), args.country)
                if not isinstance(result.get("state"), dict):
                    raise ClientError("The API export has no state object")
                content = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            else:
                state = read_json(args.input)
                if isinstance(state, dict) and isinstance(state.get("state"), dict):
                    state = state["state"]
                result = client.import_state(state)
                content = save_bytes(result)
            write_new(target, content)
            report = {"success": True, "output": str(target), "bytes": len(content)}
            if args.command == "edit":
                report["change_count"] = result.get("change_count")
        print(client.redact(json.dumps(report, ensure_ascii=False, indent=2)))
        return 0
    except (ClientError, OSError) as exc:
        message = client.redact(str(exc)) if client else "Invalid API client configuration"
        print("Error: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
