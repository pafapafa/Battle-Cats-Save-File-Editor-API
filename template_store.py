"""Immutable encrypted records in private JSONBin bins; not a distributed order lock."""
from __future__ import annotations
import base64
import hashlib
import json
import os
import re
import uuid
import zlib
import requests

ROOT = 'https://api.jsonbin.io/v3'
MAX_DOCUMENT = 3 * 1024 * 1024
CHUNK_SIZE = 60000

class StoreError(Exception):
    pass

class RecordNotFound(StoreError):
    pass

def setting(name, default=''):
    if name in os.environ:
        return os.environ[name]
    try:
        import template_secrets
        return getattr(template_secrets, name, default)
    except ImportError:
        return default

def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{24}', value) is not None

class JSONBinStore:
    def __init__(self, api_key=None, encryption_key=None, session=None):
        api_key = setting('JSONBIN_API_KEY') if api_key is None else api_key
        if not api_key:
            raise StoreError('JSONBIN_API_KEY is not configured.')
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise StoreError('Install the template encryption dependency.') from None
        key = encryption_key or setting('TEMPLATE_ENCRYPTION_KEY') or base64.urlsafe_b64encode(
            hashlib.sha256(b'bcsfe-template-v1\0' + api_key.encode()).digest())
        try:
            self.cipher = Fernet(key)
        except ValueError:
            raise StoreError('Invalid TEMPLATE_ENCRYPTION_KEY.') from None
        self.headers = {'X-Master-Key': api_key, 'X-Bin-Meta': 'true'}
        self.session = session or requests.Session()

    def call(self, method, path, **kwargs):
        headers = {**self.headers, **kwargs.pop('headers', {})}
        try:
            response = self.session.request(method, ROOT + path, headers=headers,
                                            timeout=(5, 15), allow_redirects=False, **kwargs)
            if response.status_code == 404:
                raise RecordNotFound('Record not found.')
            if response.status_code != 200:
                raise StoreError('JSONBin request failed (HTTP %s).' % response.status_code)
            return response.json()
        except (requests.RequestException, ValueError):
            raise StoreError('JSONBin request failed; its result may be uncertain.') from None

    def create_bin(self, data, name):
        result = self.call('POST', '/b', json=data, headers={
            'X-Bin-Private': 'true', 'X-Bin-Name': name, 'Content-Type': 'application/json'})
        metadata = result.get('metadata', {}) if isinstance(result, dict) else {}
        if not valid_id(metadata.get('id')) or metadata.get('private') is not True:
            raise StoreError('JSONBin did not confirm a private record.')
        return metadata['id']

    def read_bin(self, bin_id):
        if not valid_id(bin_id):
            raise RecordNotFound('Invalid record ID.')
        result = self.call('GET', '/b/' + bin_id + '/latest')
        if not isinstance(result, dict) or result.get('metadata', {}).get('private') is not True:
            raise StoreError('Expected a private backup bin.')
        record = result.get('record')
        if not isinstance(record, dict):
            raise StoreError('Invalid stored record.')
        return record

    def seal(self, value):
        raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
        if len(raw) > MAX_DOCUMENT:
            raise StoreError('Backup document is too large.')
        return self.cipher.encrypt(zlib.compress(raw)).decode('ascii')

    def unseal(self, token):
        try:
            packed = self.cipher.decrypt(token.encode('ascii'))
            inflater = zlib.decompressobj()
            raw = inflater.decompress(packed, MAX_DOCUMENT + 1)
            if len(raw) > MAX_DOCUMENT or not inflater.eof or inflater.unused_data:
                raise ValueError('Invalid compressed document')
            return json.loads(raw)
        except Exception:
            raise StoreError('Backup integrity check failed.') from None

    def save(self, kind, value):
        token = self.seal({'kind': kind, 'data': value})
        name = 'bcsfe-' + kind + '-' + uuid.uuid4().hex
        if len(token) <= CHUNK_SIZE:
            root = {'format': 'bcsfe-v1', 'payload': token}
        else:
            chunk_ids = []
            for offset in range(0, len(token), CHUNK_SIZE):
                chunk_ids.append(self.create_bin({'format': 'bcsfe-chunk-v1',
                    'payload': token[offset:offset + CHUNK_SIZE]}, 'bcsfe-chunk-' + uuid.uuid4().hex))
            root = {'format': 'bcsfe-manifest-v1', 'payload': self.seal({'chunks': chunk_ids})}
        # No source bin is ever updated. The root is created after all chunks.
        return self.create_bin(root, name)

    def load(self, bin_id, kind):
        root = self.read_bin(bin_id)
        if root.get('format') == 'bcsfe-manifest-v1':
            parts = self.unseal(root['payload']).get('chunks', [])
            if not isinstance(parts, list) or not 1 <= len(parts) <= 72 or not all(valid_id(p) for p in parts):
                raise StoreError('Invalid backup manifest.')
            tokens = []
            for part in parts:
                chunk = self.read_bin(part)
                if chunk.get('format') != 'bcsfe-chunk-v1' or not isinstance(chunk.get('payload'), str) or len(chunk['payload']) > CHUNK_SIZE:
                    raise StoreError('Invalid backup chunk.')
                tokens.append(chunk['payload'])
            token = ''.join(tokens)
        elif root.get('format') == 'bcsfe-v1':
            token = root.get('payload', '')
        else:
            raise RecordNotFound('This bin is not a BCSFE backup.')
        value = self.unseal(token)
        if not isinstance(value, dict) or value.get('kind') != kind or not isinstance(value.get('data'), dict):
            raise RecordNotFound('Record type does not match.')
        return value['data']

    def list_records(self, kind, cursor=''):
        if cursor and not valid_id(cursor):
            raise RecordNotFound('Invalid cursor.')
        page = self.call('GET', '/c/uncategorized/bins' + ('/' + cursor if cursor else ''))
        if not isinstance(page, list):
            raise StoreError('Invalid JSONBin listing.')
        items = []
        for item in page:
            if isinstance(item, dict) and str(item.get('snippetMeta', {}).get('name', '')).startswith('bcsfe-' + kind + '-'):
                items.append({'id': item['record'], 'created_at': item.get('createdAt')})
        return {'records': items, 'next_cursor': page[-1]['record'] if len(page) == 10 else None}


    def list_templates(self, cursor=''):
        page = self.list_records('template', cursor)
        return {'templates': [{'template_id': r['id'], 'created_at': r['created_at']} for r in page['records']],
                'next_cursor': page['next_cursor']}
