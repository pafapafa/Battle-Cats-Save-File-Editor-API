from std.python import Python
from std.sys import argv


def main() raises:
    arguments = Python.list()
    for argument in argv():
        arguments.append(String(argument))
    scope = Python.dict()
    scope["arguments"] = arguments
    Python.import_module("builtins").exec("""
import http.client
import json
import os
import pathlib
import sys
import time
import urllib.parse

MAX_BYTES = 2 * 1024 * 1024

def run(arguments):
    if len(arguments) != 3:
        raise ValueError('Usage: mojo example.mojo REQUEST_JSON OUTPUT_SAVE')
    input_path, output_path = map(pathlib.Path, arguments[1:])
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError('Output already exists')
    token = os.environ.get('EDITOR_API_KEY', '').strip() or os.environ.get('TEMPLATE_API_KEY', '').strip()
    if not token:
        raise ValueError('Set EDITOR_API_KEY or TEMPLATE_API_KEY')
    base = os.environ.get('BCSFE_API_URL') or 'https://battle-cats-save-file-editor-api.vercel.app'
    url = urllib.parse.urlsplit(base.rstrip('/') + '/v2/save/edit')
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('BCSFE_API_URL must be an HTTP(S) base URL without credentials, query, or fragment')
    if input_path.stat().st_size > MAX_BYTES:
        raise ValueError('Request exceeds 2 MiB')
    body = input_path.read_bytes()
    if len(body) > MAX_BYTES:
        raise ValueError('Request exceeds 2 MiB')
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError('Request must be valid UTF-8 JSON') from None
    if not isinstance(payload, dict) or payload.get('output') != 'file' or not isinstance(payload.get('country_code'), str) or not isinstance(payload.get('save_base64'), str) or not isinstance(payload.get('operations'), list):
        raise ValueError('Request needs country_code, save_base64, operations, and output:file')
    transport = http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection
    connection = transport(url.hostname, url.port, timeout=15)
    deadline = time.monotonic() + 120
    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError('Request timed out')
        return value
    data = bytearray()
    response = None
    try:
        connection.connect()
        active_socket = connection.sock
        active_socket.settimeout(remaining())
        connection.request('POST', url.path, body=body, headers={
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json',
            'Accept': 'application/octet-stream',
        })
        active_socket.settimeout(remaining())
        response = connection.getresponse()
        content_type = response.getheader('Content-Type', '').split(';', 1)[0].strip().lower()
        if not 200 <= response.status < 300 or content_type != 'application/octet-stream':
            raise ValueError('Expected a binary success response; HTTP ' + str(response.status))
        expected_length = response.length
        while not response.isclosed():
            active_socket.settimeout(remaining())
            chunk = response.read1(65536)
            if not chunk:
                break
            if len(data) + len(chunk) > MAX_BYTES:
                raise ValueError('Response exceeds 2 MiB')
            data.extend(chunk)
        if expected_length is not None and len(data) != expected_length:
            raise ValueError('Incomplete binary response')
    finally:
        if response is not None:
            response.close()
        connection.close()
    created = False
    try:
        with output_path.open('xb') as output:
            created = True
            output.write(data)
            output.flush()
    except BaseException:
        if created:
            output_path.unlink()
        raise
    print('Saved', len(data), 'bytes to', output_path)

try:
    run(arguments)
except (OSError, ValueError, http.client.HTTPException) as error:
    print(str(error), file=sys.stderr)
    sys.exit(1)
""", scope)
