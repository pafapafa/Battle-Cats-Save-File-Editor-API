import base64
import hashlib
import io
import json
import os
import unittest
from unittest.mock import patch

from flask import Flask
from jsonschema import Draft202012Validator

from template_api import register_template_api
from template_store import JSONBinStore
from test_templates import BinSession, Handler, MemoryStore, TOKEN, fixture


class BackupAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = fixture()

    def setUp(self):
        settings = patch.dict(os.environ, {'TEMPLATE_API_KEY': '', 'JSONBIN_API_KEY': ''})
        settings.start()
        self.addCleanup(settings.stop)
        self.vault = MemoryStore()
        self.handlers = []
        self.failure = None

        def handler_factory(sf):
            handler = Handler(sf)
            handler.failure = self.failure
            self.handlers.append(handler)
            return handler

        self.app = Flask(__name__)
        self.spec = {'paths': {}}
        register_template_api(self.app, self.spec)
        self.app.config.update(TESTING=True, TEMPLATE_STORE_FACTORY=lambda: self.vault,
                               TEMPLATE_HANDLER_FACTORY=handler_factory)
        self.client = self.app.test_client()

    def upload(self):
        response = self.client.post('/v1/templates', json={
            'save_base64': base64.b64encode(self.raw).decode(), 'country_code': 'auto'})
        self.assertEqual(201, response.status_code, response.get_json())
        return response.get_json()

    def headers(self, created):
        return {'X-Backup-Token': created['backup_token']}

    def clone(self, created):
        response = self.client.post('/v1/templates/' + created['template_id'] + '/clones',
                                    json={'order_id': 'order-1'}, headers=self.headers(created))
        return response

    def test_anonymous_creation_private_download_and_one_time_token(self):
        first, second = self.upload(), self.upload()
        self.assertNotEqual(first['backup_token'], second['backup_token'])
        self.assertRegex(first['backup_token'], r'^[A-Za-z0-9_-]{43}$')
        schema = self.spec['paths']['/v1/templates']['post']['responses']['201']['content']['application/json']['schema']
        Draft202012Validator({'components': self.spec['components'], 'allOf': [schema]}).validate(first)
        stored = self.vault.load(first['template_id'], 'template')
        self.assertEqual(hashlib.sha256(first['backup_token'].encode()).hexdigest(), stored['backup_token_sha256'])
        self.assertNotIn(first['backup_token'], json.dumps(stored))
        metadata = self.client.get('/v1/templates/' + first['template_id'], headers=self.headers(first))
        self.assertEqual(200, metadata.status_code)
        self.assertNotIn('backup_token', metadata.get_json())
        self.assertNotIn('backup_token_sha256', metadata.get_json())
        self.assertNotIn('save_base64', metadata.get_json())
        downloaded = self.client.get('/v1/templates/' + first['template_id'] + '/download', headers=self.headers(first))
        self.assertEqual(200, downloaded.status_code)
        self.assertEqual(self.raw, downloaded.data)
        self.assertEqual('no-store', downloaded.headers['Cache-Control'])
        self.assertEqual([], self.handlers)

    def test_all_private_paths_require_the_associated_backup_token(self):
        first, second = self.upload(), self.upload()
        issued_response = self.clone(first)
        self.assertEqual(201, issued_response.status_code, issued_response.get_json())
        issued = issued_response.get_json()
        routes = [
            ('GET', '/v1/templates/' + first['template_id']),
            ('GET', '/v1/templates/' + first['template_id'] + '/download'),
            ('POST', '/v1/templates/' + first['template_id'] + '/clones'),
            ('GET', '/v1/attempts/' + issued['attempt_id']),
            ('GET', '/v1/recoveries/' + issued['recovery_id']),
            ('GET', '/v1/recoveries/' + issued['recovery_id'] + '/download'),
            ('GET', '/v1/issuances/' + issued['issuance_id']),
        ]
        expected = {'success': False, 'message': 'Record not found.'}
        for method, path in routes:
            for supplied in ({}, self.headers(second), {'X-Backup-Token': 'x' * 43}, {'Authorization': 'Bearer ' + TOKEN}):
                with self.subTest(method=method, path=path, supplied=list(supplied)):
                    response = self.client.open(path, method=method, headers=supplied, json={'order_id': 'order-2'})
                    self.assertEqual(404, response.status_code)
                    self.assertEqual(expected, response.get_json())
            if method == 'GET':
                allowed = self.client.get(path, headers=self.headers(first))
                self.assertEqual(200, allowed.status_code)
                if allowed.is_json:
                    text = allowed.get_data(as_text=True)
                    self.assertNotIn(first['backup_token'], text)
                    self.assertNotIn('backup_token_sha256', text)
        self.assertEqual(1, len(self.handlers))
        self.assertEqual(['create', 'items', 'codes'], self.handlers[0].calls)
        for identifier in ('not-an-id', 'f' * 24, issued['recovery_id']):
            response = self.client.get('/v1/templates/' + identifier, headers=self.headers(first))
            self.assertEqual(404, response.status_code)
            self.assertEqual(expected, response.get_json())
        self.assertNotIn(first['backup_token'], json.dumps(issued))
        self.assertNotIn('backup_token_sha256', json.dumps(issued))

    def test_tokens_in_url_or_body_do_not_authorize_a_request(self):
        created = self.upload()
        path = '/v1/templates/' + created['template_id']
        for query in ('backup_token', 'token', 'X-Backup-Token'):
            response = self.client.get(path, query_string={query: created['backup_token']})
            self.assertEqual(404, response.status_code)
        response = self.client.post(path + '/clones', json={
            'backup_token': created['backup_token'], 'order_id': 'order-1'})
        self.assertEqual(404, response.status_code)
        self.assertEqual([], self.handlers)

    def test_anonymous_file_backup_needs_neither_admin_key_nor_storage(self):
        with patch('template_api.store', side_effect=AssertionError('Storage must not be accessed')):
            response = self.client.post('/v1/backups', data={
                'file': (io.BytesIO(self.raw), 'save.dat'), 'country_code': 'auto'})
        self.assertEqual(200, response.status_code)
        self.assertEqual(self.raw, response.data)
        self.assertEqual({}, self.vault.items)
        self.assertEqual([], self.handlers)

    def test_global_lists_remain_admin_only_and_old_records_need_admin(self):
        self.vault = JSONBinStore(api_key='fake-jsonbin-key', session=BinSession())
        created = self.upload()
        old_record = self.vault.load(created['template_id'], 'template')
        old_record.pop('backup_token_sha256')
        old_id = self.vault.save('template', old_record)
        for key in ('', 'too-short', TOKEN):
            with patch.dict(os.environ, {'TEMPLATE_API_KEY': key}):
                for path in ('/v1/templates', '/v1/template-records'):
                    for headers in ({}, self.headers(created)):
                        self.assertEqual(403, self.client.get(path, headers=headers).status_code)
                self.assertEqual(404, self.client.get('/v1/templates/' + old_id, headers=self.headers(created)).status_code)
        with patch.dict(os.environ, {'TEMPLATE_API_KEY': TOKEN}):
            headers = {'Authorization': 'Bearer ' + TOKEN}
            for path in ('/v1/templates', '/v1/template-records', '/v1/templates/' + old_id):
                self.assertEqual(200, self.client.get(path, headers=headers).status_code)
            created_as_admin = self.client.post('/v1/templates', json={
                'save_base64': base64.b64encode(self.raw).decode()}, headers=headers)
            self.assertEqual(201, created_as_admin.status_code)
            self.assertRegex(created_as_admin.get_json()['backup_token'], r'^[A-Za-z0-9_-]{43}$')
        self.assertEqual(200, self.client.get('/v1/templates/' + created['template_id'], headers=self.headers(created)).status_code)

    def test_storage_contains_only_encrypted_token_hash(self):
        session = BinSession()
        self.vault = JSONBinStore(api_key='fake-jsonbin-key', session=session)
        created = self.upload()
        stored = self.vault.load(created['template_id'], 'template')
        wire = json.dumps(session.records)
        self.assertNotIn(created['backup_token'], wire)
        self.assertNotIn(stored['backup_token_sha256'], wire)
        self.assertNotIn('backup_token_sha256', wire)
        self.assertNotIn('save_base64', wire)
        response = self.client.get('/v1/templates/' + created['template_id'] + '/download', headers=self.headers(created))
        self.assertEqual(self.raw, response.data)

    def test_failed_issuance_recovery_remains_accessible_only_to_its_backup(self):
        created, other = self.upload(), self.upload()
        self.failure = 'codes'
        result = self.clone(created)
        self.assertEqual(502, result.status_code)
        body = result.get_json()
        self.assertFalse(body['retry_safe'])
        self.assertEqual(self.raw, base64.b64decode(body['backup_base64']))
        self.assertNotIn(created['backup_token'], json.dumps(body))
        path = '/v1/recoveries/' + body['recovery_id'] + '/download'
        self.assertEqual(404, self.client.get(path, headers=self.headers(other)).status_code)
        recovered = self.client.get(path, headers=self.headers(created))
        self.assertEqual(200, recovered.status_code)
        self.assertEqual(base64.b64decode(body['save_base64']), recovered.data)
        self.assertEqual(1, len(self.handlers))


if __name__ == '__main__':
    unittest.main()
