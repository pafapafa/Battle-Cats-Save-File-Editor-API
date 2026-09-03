import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import requests
from flask import Flask
from jsonschema import Draft202012Validator, ValidationError
from bcsfe import core
from bcsfe.core.game.catbase.cat import Talent
from template_api import register_template_api
from template_store import JSONBinStore, StoreError, RecordNotFound
from examples.vending_backend import issue_once, OrderNeedsAttention

TOKEN = 'test-template-key-' + 'x' * 32

def fixture(country='kr'):
    sf = core.SaveFile(cc=core.CountryCode.from_code(country), gv=core.GameVersion(150500), load=False)
    sf.inquiry_code = 'original-account'
    sf.xp = 9876
    sf.catfood = 321
    sf.officer_pass.play_time = 123456
    sf.officer_pass.gold_pass.officer_id = 123
    sf.lineups.slots[0].slots[0].cat_id = 2
    sf.gamatoto.skin = 1
    sf.cats = core.Cats([core.Cat(0, 1), core.Cat(1, 1), core.Cat(2, 1)], 100)
    sf.cats.cats[0].talents = [Talent(1, 1)]
    return sf.to_data().data

class Response:
    status_code = 200
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status
    def json(self):
        return copy.deepcopy(self.data)

class BinSession:
    def __init__(self):
        self.records = {}
        self.names = {}
        self.calls = []
        self.fail_kind = None
    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        assert url.startswith('https://api.jsonbin.io/v3/')
        assert kwargs['allow_redirects'] is False
        assert kwargs['headers']['X-Master-Key'] == 'fake-jsonbin-key'
        path = url.split('/v3', 1)[1]
        if method == 'POST':
            assert kwargs['headers']['X-Bin-Private'] == 'true'
            assert len(json.dumps(kwargs['json']).encode()) < 100000
            bid = '%024x' % (len(self.records) + 1)
            self.records[bid] = copy.deepcopy(kwargs['json'])
            self.names[bid] = kwargs['headers']['X-Bin-Name']
            return Response({'record': kwargs['json'], 'metadata': {'id': bid, 'private': True}})
        if path.startswith('/c/'):
            return Response([{'record': bid, 'private': True, 'createdAt': 'today',
                              'snippetMeta': {'name': self.names[bid]}}
                             for bid in reversed(self.records)])
        bid = path.split('/')[2]
        if bid not in self.records:
            return Response({}, 404)
        return Response({'record': self.records[bid], 'metadata': {'id': bid, 'private': True}})

class MemoryStore:
    def __init__(self):
        self.items = {}
        self.fail = None
    def save(self, kind, value):
        if kind == self.fail:
            raise StoreError('Synthetic storage failure')
        bid = '%024x' % (len(self.items) + 1)
        self.items[bid] = (kind, copy.deepcopy(value))
        return bid
    def load(self, bid, kind):
        if bid not in self.items or self.items[bid][0] != kind:
            raise RecordNotFound('Missing record')
        return copy.deepcopy(self.items[bid][1])
    def list_templates(self, cursor=''):
        return {'templates': [{'template_id': k} for k, v in self.items.items() if v[0]=='template'], 'next_cursor': None}

class Handler:
    def __init__(self, sf):
        self.save_file = sf
        self.calls = []
        self.failure = None
    def create_new_account(self, tries):
        self.calls.append('create')
        assert tries == 1
        if self.failure == 'create':
            return False
        if self.failure != 'identity':
            self.save_file.inquiry_code = 'new-account'
        return self.update_managed_items()
    def update_managed_items(self):
        self.calls.append('items')
        return self.failure != 'items'
    def get_codes(self, tries):
        self.calls.append('codes')
        assert tries == 1
        return None if self.failure == 'codes' else ('synthetic-transfer', '1234')

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.session = BinSession()
        self.store = JSONBinStore(api_key='fake-jsonbin-key', session=self.session)
    def test_encrypt_and_roundtrip(self):
        value = {'save_base64': 'DO-NOT-EXPOSE-THIS', 'label': '한국어'}
        bid = self.store.save('template', value)
        self.assertEqual(value, self.store.load(bid, 'template'))
        self.assertNotIn('DO-NOT-EXPOSE-THIS', json.dumps(self.session.records))
        self.assertEqual(bid, self.store.list_templates()['templates'][0]['template_id'])
    def test_large_record_chunks_below_free_limit(self):
        value = {'data': base64.b64encode(os.urandom(180000)).decode()}
        bid = self.store.save('template', value)
        self.assertGreater(len(self.session.records), 3)
        self.assertEqual(value, self.store.load(bid, 'template'))
    def test_tamper_rejected(self):
        bid = self.store.save('template', {'foo': 'bar'})
        self.session.records[bid]['payload'] = 'bad'
        with self.assertRaises(StoreError):
            self.store.load(bid, 'template')
    def test_wrong_key_rejected(self):
        bid = self.store.save('template', {'foo': 'bar'})
        other = JSONBinStore(api_key='fake-jsonbin-key', encryption_key=base64.urlsafe_b64encode(b'1'*32), session=self.session)
        with self.assertRaises(StoreError):
            other.load(bid, 'template')
    def test_wrong_kind_rejected(self):
        bid = self.store.save('attempt', {'foo': 'bar'})
        with self.assertRaises(RecordNotFound):
            self.store.load(bid, 'template')
    def test_private_confirmation_required(self):
        with patch.object(self.session, 'request', return_value=Response({'metadata': {'id': 'a'*24, 'private': False}})):
            with self.assertRaises(StoreError):
                self.store.save('template', {'foo': 'bar'})
    def test_no_retry_on_write_timeout(self):
        with patch.object(self.session, 'request', side_effect=requests.Timeout()) as call:
            with self.assertRaises(StoreError):
                self.store.save('template', {'foo': 'bar'})
            self.assertEqual(1, call.call_count)

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = fixture()
    def setUp(self):
        self.settings = patch.dict(os.environ, {'TEMPLATE_API_KEY': TOKEN})
        self.settings.start()
        self.vault = MemoryStore()
        self.handlers = []
        self.failure = None
        def factory(sf):
            h = Handler(sf)
            h.failure = self.failure
            self.handlers.append(h)
            return h
        app = Flask(__name__)
        self.spec = {'paths': {}}
        register_template_api(app, self.spec)
        app.config.update(TESTING=True, TEMPLATE_STORE_FACTORY=lambda: self.vault, TEMPLATE_HANDLER_FACTORY=factory)
        self.client = app.test_client()
        self.headers = {'Authorization': 'Bearer ' + TOKEN}
    def tearDown(self):
        self.settings.stop()
    def upload(self):
        r = self.client.post('/v1/templates', json={'save_base64': base64.b64encode(self.raw).decode(),
                                                  'name': 'Starter', 'country_code': 'kr'}, headers=self.headers)
        self.assertEqual(201, r.status_code, r.get_json())
        return r.get_json()['template_id']
    def clone(self, bid):
        return self.client.post('/v1/templates/' + bid + '/clones', json={'order_id': 'order-1'}, headers=self.headers)
    def test_requires_authentication(self):
        self.assertEqual(401, self.client.get('/v1/templates').status_code)
    def test_missing_config_is_503(self):
        with patch.dict(os.environ, {'TEMPLATE_API_KEY': ''}):
            self.assertEqual(503, self.client.get('/v1/templates').status_code)
    def test_exact_file_download_and_metadata(self):
        bid = self.upload()
        result = self.client.get('/v1/templates/' + bid + '/download', headers=self.headers)
        self.assertEqual(self.raw, result.data)
        self.assertEqual('no-store', result.headers['Cache-Control'])
        metadata = self.client.get('/v1/templates/' + bid, headers=self.headers).get_json()
        self.assertTrue(metadata['clone_ready'])
        self.assertNotIn('save_base64', metadata)
        self.assertNotIn('original-account', json.dumps(metadata))
    def test_multipart_backup_needs_no_storage(self):
        self.vault.fail = 'template'
        result = self.client.post('/v1/backups', data={'file': (io.BytesIO(self.raw), 'save.dat'), 'country_code': 'kr'}, headers=self.headers)
        self.assertEqual(200, result.status_code)
        self.assertEqual(self.raw, result.data)
        self.assertEqual({}, self.vault.items)
    def test_auto_region_all_four_regions_and_both_upload_formats(self):
        with patch('builtins.input', side_effect=AssertionError('Interactive input forbidden')) as prompt, \
             patch.object(core.CountryCode, 'select', side_effect=AssertionError('Country selector forbidden')) as selector, \
             patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')) as network:
            for country in ('kr', 'en', 'jp', 'tw'):
                raw = fixture(country)
                for multipart in (False, True):
                    with self.subTest(country=country, multipart=multipart):
                        def upload_args():
                            if multipart:
                                return {'data': {'file': (io.BytesIO(raw), 'save.dat'), 'country_code': 'auto'}}
                            return {'json': {'save_base64': base64.b64encode(raw).decode(), 'country_code': 'auto'}}
                        response = self.client.post('/v1/templates', headers=self.headers, **upload_args())
                        self.assertEqual(201, response.status_code, response.get_json())
                        metadata = response.get_json()
                        self.assertEqual(country, metadata['country_code'])
                        self.assertTrue(metadata['clone_ready'])
                        record = self.vault.load(metadata['template_id'], 'template')
                        self.assertEqual(country, record['country_code'])
                        self.assertEqual(raw, base64.b64decode(record['save_base64']))
                        backup = self.client.post('/v1/backups', headers=self.headers, **upload_args())
                        self.assertEqual(200, backup.status_code, backup.get_json())
                        self.assertEqual(raw, backup.data)
            prompt.assert_not_called()
            selector.assert_not_called()
            network.assert_not_called()
            self.assertEqual([], self.handlers)

    def test_auto_invalid_checksum_is_422_without_storage_or_prompts(self):
        corrupted = bytearray(self.raw)
        corrupted[20] ^= 1
        with patch('builtins.input', side_effect=AssertionError('Interactive input forbidden')) as prompt, \
             patch.object(core.CountryCode, 'select', side_effect=AssertionError('Country selector forbidden')) as selector, \
             patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')) as network:
            for raw in (b'x' * 50, bytes(corrupted)):
                for path in ('/v1/templates', '/v1/backups'):
                    for multipart in (False, True):
                        with self.subTest(path=path, multipart=multipart, length=len(raw)):
                            if multipart:
                                args = {'data': {'file': (io.BytesIO(raw), 'save.dat'), 'country_code': 'auto'}}
                            else:
                                args = {'json': {'save_base64': base64.b64encode(raw).decode(), 'country_code': 'auto'}}
                            response = self.client.post(path, headers=self.headers, **args)
                            self.assertEqual(422, response.status_code, response.get_json())
            prompt.assert_not_called()
            selector.assert_not_called()
            network.assert_not_called()
            self.assertEqual({}, self.vault.items)
            self.assertEqual([], self.handlers)

    def test_omitted_country_keeps_kr_default_and_explicit_mismatch_rejects(self):
        response = self.client.post('/v1/templates', json={'save_base64': base64.b64encode(self.raw).decode()}, headers=self.headers)
        self.assertEqual(201, response.status_code)
        self.assertEqual('kr', response.get_json()['country_code'])
        en = fixture('en')
        for multipart in (False, True):
            for path in ('/v1/templates', '/v1/backups'):
                with self.subTest(path=path, multipart=multipart):
                    if multipart:
                        args = {'data': {'file': (io.BytesIO(en), 'save.dat'), 'country_code': 'kr'}}
                    else:
                        args = {'json': {'save_base64': base64.b64encode(en).decode(), 'country_code': 'kr'}}
                    response = self.client.post(path, headers=self.headers, **args)
                    self.assertEqual(422, response.status_code)
        response = self.client.post('/v1/templates', json={'save_base64': base64.b64encode(en).decode()}, headers=self.headers)
        self.assertEqual(422, response.status_code)
        self.assertEqual(1, len(self.vault.items))

    def test_region_mismatch(self):
        r = self.client.post('/v1/templates', json={'save_base64': base64.b64encode(self.raw).decode(), 'country_code': 'en'}, headers=self.headers)
        self.assertEqual(422, r.status_code)
    def test_invalid_base64(self):
        r = self.client.post('/v1/templates', json={'save_base64': 'invalid??'}, headers=self.headers)
        self.assertEqual(400, r.status_code)
    def test_invalid_save(self):
        r = self.client.post('/v1/templates', json={'save_base64': base64.b64encode(b'x'*50).decode()}, headers=self.headers)
        self.assertEqual(422, r.status_code)
    def test_store_failure_not_success(self):
        self.vault.fail = 'template'
        r = self.client.post('/v1/templates', json={'save_base64': base64.b64encode(self.raw).decode()}, headers=self.headers)
        self.assertEqual(503, r.status_code)
    def test_clone_preserves_source_and_game_fields(self):
        bid = self.upload()
        before = copy.deepcopy(self.vault.items[bid])
        r = self.clone(bid)
        self.assertEqual(201, r.status_code, r.get_json())
        self.assertTrue(r.get_json()['persisted'])
        self.assertEqual(before, self.vault.items[bid])
        sf = self.handlers[0].save_file
        self.assertEqual('new-account', sf.inquiry_code)
        self.assertEqual((9876, 321, 123456, 2, 1), (sf.xp, sf.catfood, sf.officer_pass.play_time,
                        sf.lineups.slots[0].slots[0].cat_id, sf.gamatoto.skin))
        saved = self.client.get('/v1/issuances/' + r.get_json()['issuance_id'], headers=self.headers).get_json()
        self.assertEqual('synthetic-transfer', saved['transfer_code'])
    def test_false_create_identity_items_codes_not_success(self):
        for failure in ('create', 'identity', 'items', 'codes'):
            with self.subTest(failure=failure):
                self.failure = failure
                r = self.clone(self.upload())
                self.assertEqual(502, r.status_code)
                self.assertFalse(r.get_json()['success'])
                self.assertFalse(r.get_json()['retry_safe'])
    def test_failed_attempt_storage_prevents_account_call(self):
        bid = self.upload()
        self.vault.fail = 'attempt'
        r = self.clone(bid)
        self.assertEqual(503, r.status_code)
        self.assertEqual([], self.handlers[0].calls)
    def test_failed_recovery_storage_prevents_code_call(self):
        bid = self.upload()
        self.vault.fail = 'recovery'
        r = self.clone(bid)
        self.assertEqual(502, r.status_code)
        self.assertNotIn('codes', self.handlers[0].calls)
        self.assertEqual(base64.b64decode(r.json['backup_base64']),self.raw)
        restored=core.SaveFile(core.Data(base64.b64decode(r.json['save_base64'])))
        self.assertEqual(restored.inquiry_code,'new-account')
        self.assertTrue(r.json['recovery_serialized'])
    def test_codes_returned_if_final_storage_fails(self):
        bid = self.upload()
        self.vault.fail = 'issuance'
        r = self.clone(bid)
        self.assertEqual(201, r.status_code)
        self.assertFalse(r.get_json()['persisted'])
        self.assertEqual('synthetic-transfer', r.get_json()['transfer_code'])
    def test_order_id_required(self):
        r = self.client.post('/v1/templates/' + self.upload() + '/clones', json={}, headers=self.headers)
        self.assertEqual(400, r.status_code)
    def test_non_roundtrippable_save_never_sent(self):
        bid = self.upload()
        with patch('template_api.parse_save') as parse:
            parse.return_value.to_data.return_value.data = b'different'
            r = self.clone(bid)
        self.assertEqual(422, r.status_code)
        self.assertEqual([], self.handlers)
    def validate_documented_response(self, path, method, response):
        operation = self.spec['paths'][path][method]
        schema = operation['responses'][str(response.status_code)]['content']['application/json']['schema']
        document = {'components': self.spec['components'], 'allOf': [schema]}
        Draft202012Validator(document).validate(response.get_json())
        return response.get_json()

    def test_openapi_matches_real_metadata_lists_records_and_binary_responses(self):
        # Exercise real JSONBinStore record/list shapes using an in-memory HTTP session.
        self.vault = JSONBinStore(api_key='fake-jsonbin-key', session=BinSession())
        for schema in self.spec['components']['schemas'].values():
            Draft202012Validator.check_schema(schema)
        uploaded = self.client.post('/v1/templates', json={'save_base64': base64.b64encode(self.raw).decode(), 'country_code': 'auto'}, headers=self.headers)
        metadata = self.validate_documented_response('/v1/templates', 'post', uploaded)
        bid = metadata['template_id']
        listed = self.validate_documented_response('/v1/templates', 'get', self.client.get('/v1/templates', headers=self.headers))
        self.assertEqual([bid], [item['template_id'] for item in listed['templates']])
        self.validate_documented_response('/v1/templates/{template_id}', 'get', self.client.get('/v1/templates/' + bid, headers=self.headers))
        issued = self.validate_documented_response('/v1/templates/{template_id}/clones', 'post', self.clone(bid))
        self.assertTrue(issued['persisted'])
        for kind, plural in [('attempt', 'attempts'), ('recovery', 'recoveries'), ('issuance', 'issuances')]:
            with self.subTest(kind=kind):
                listing = self.validate_documented_response('/v1/template-records', 'get', self.client.get('/v1/template-records?kind=' + kind, headers=self.headers))
                self.assertEqual([issued[kind + '_id']], [item['id'] for item in listing['records']])
                route = '/v1/' + plural + '/{' + kind + '_id}'
                response = self.client.get('/v1/' + plural + '/' + issued[kind + '_id'], headers=self.headers)
                details = self.validate_documented_response(route, 'get', response)
                self.assertNotIn('save_base64', details)
                if kind == 'issuance':
                    self.assertNotIn('persisted', details)
                    self.assertNotIn('retry_safe', details)
        downloads = [
            ('/v1/backups', 'post', self.client.post('/v1/backups', data={'file': (io.BytesIO(self.raw), 'save.dat')}, headers=self.headers)),
            ('/v1/templates/{template_id}/download', 'get', self.client.get('/v1/templates/' + bid + '/download', headers=self.headers)),
            ('/v1/recoveries/{recovery_id}/download', 'get', self.client.get('/v1/recoveries/' + issued['recovery_id'] + '/download', headers=self.headers)),
        ]
        for path, method, response in downloads:
            with self.subTest(path=path):
                self.assertEqual(200, response.status_code)
                self.assertEqual('application/octet-stream', response.mimetype)
                self.assertTrue(response.headers['Content-Disposition'].startswith('attachment;'))
                declared = self.spec['paths'][path][method]['responses']['200']['content']
                self.assertEqual({'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}}}, declared)
                if path != '/v1/recoveries/{recovery_id}/download':
                    self.assertEqual(self.raw, response.data)

    def test_openapi_matches_clone_unpersisted_and_both_recovery_failure_shapes(self):
        path = '/v1/templates/{template_id}/clones'
        bid = self.upload()
        self.vault.fail = 'issuance'
        issued = self.validate_documented_response(path, 'post', self.clone(bid))
        self.assertFalse(issued['persisted'])
        self.assertNotIn('issuance_id', issued)
        wrong = copy.deepcopy(issued)
        wrong['persisted'] = True
        schema = self.spec['paths'][path]['post']['responses']['201']['content']['application/json']['schema']
        with self.assertRaises(ValidationError):
            Draft202012Validator({'components': self.spec['components'], 'allOf': [schema]}).validate(wrong)
        self.vault.fail = None
        for failure in ('create', 'codes'):
            with self.subTest(failure=failure):
                self.failure = failure
                response = self.clone(bid)
                self.assertEqual(502, response.status_code)
                result = self.validate_documented_response(path, 'post', response)
                self.assertEqual(self.raw, base64.b64decode(result['backup_base64']))
                self.assertEqual(failure == 'create', result['recovery_id'] is None)

    def test_openapi_request_rules_preserve_trimmed_names_and_exact_order_ids(self):
        schema = self.spec['paths']['/v1/templates']['post']['requestBody']['content']['application/json']['schema']
        request_data = {'save_base64': base64.b64encode(self.raw).decode(), 'name': ' ' * 110 + 'Valid' + ' ' * 110}
        Draft202012Validator(schema).validate(request_data)
        response = self.client.post('/v1/templates', json=request_data, headers=self.headers)
        self.assertEqual(201, response.status_code)
        self.assertEqual('Valid', response.get_json()['name'])
        bid = response.get_json()['template_id']
        order_schema = self.spec['paths']['/v1/templates/{template_id}/clones']['post']['requestBody']['content']['application/json']['schema']
        Draft202012Validator(order_schema).validate({'order_id': 'order_1:ABC.2-3'})
        for value in ('order\n', '', 'x' * 101, 'order/1'):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    Draft202012Validator(order_schema).validate({'order_id': value})
                response = self.client.post('/v1/templates/' + bid + '/clones', json={'order_id': value}, headers=self.headers)
                self.assertEqual(400, response.status_code)
                self.validate_documented_response('/v1/templates/{template_id}/clones', 'post', response)
        self.assertEqual([], self.handlers)

    def test_openapi_error_payloads_match_http_statuses(self):
        samples = [
            ('/v1/templates', 'get', self.client.get('/v1/templates')),
            ('/v1/templates/{template_id}', 'get', self.client.get('/v1/templates/not-an-id', headers=self.headers)),
            ('/v1/templates', 'post', self.client.post('/v1/templates', json={'save_base64': base64.b64encode(b'x' * 50).decode(), 'country_code': 'auto'}, headers=self.headers)),
            ('/v1/templates', 'post', self.client.post('/v1/templates', json={'save_base64': 'a' * 1398105}, headers=self.headers)),
        ]
        self.assertEqual([401, 404, 422, 413], [response.status_code for _, _, response in samples])
        for path, method, response in samples:
            with self.subTest(status=response.status_code):
                self.validate_documented_response(path, method, response)

    def test_openapi_security_and_upload_types(self):
        op = self.spec['paths']['/v1/templates']['post']
        self.assertEqual([{'TemplateToken': []}], op['security'])
        self.assertIn('multipart/form-data', op['requestBody']['content'])
        for path in ('/v1/templates', '/v1/backups'):
            content = self.spec['paths'][path]['post']['requestBody']['content']
            for media in ('application/json', 'multipart/form-data'):
                with self.subTest(path=path, media=media):
                    country = content[media]['schema']['properties']['country_code']
                    self.assertEqual(['auto', 'kr', 'en', 'jp', 'tw'], country['enum'])
                    self.assertEqual('kr', country['default'])
                    self.assertIn('checksum', country['description'])

class OrderTests(unittest.TestCase):
    def test_duplicate_order_reuses_result(self):
        with tempfile.TemporaryDirectory() as temp:
            client = unittest.mock.Mock()
            client.post.return_value = Response({'success': True, 'status': 'issued',
                'transfer_code': 'synthetic', 'confirmation_code': '1234'}, 201)
            args = ('https://example.invalid', TOKEN, 'a'*24, 'order-1', str(Path(temp)/'orders.sqlite'))
            self.assertEqual(issue_once(*args, session=client), issue_once(*args, session=client))
            self.assertEqual(1, client.post.call_count)
            with self.assertRaises(ValueError):
                issue_once(args[0], TOKEN, 'b'*24, 'order-1', args[-1], session=client)
    def test_timeout_never_reissued(self):
        with tempfile.TemporaryDirectory() as temp:
            client = unittest.mock.Mock()
            client.post.side_effect = requests.Timeout()
            args = ('https://example.invalid', TOKEN, 'a'*24, 'order-1', str(Path(temp)/'orders.sqlite'))
            for _ in range(2):
                with self.assertRaises(OrderNeedsAttention):
                    issue_once(*args, session=client)
            self.assertEqual(1, client.post.call_count)
    def test_concurrent_order_only_one_outbound_call(self):
        with tempfile.TemporaryDirectory() as temp:
            entered, release = threading.Event(), threading.Event()
            results = []
            client = unittest.mock.Mock()
            def post(*a, **k):
                entered.set()
                release.wait(5)
                return Response({'success': True, 'status': 'issued',
                    'transfer_code': 'synthetic', 'confirmation_code': '1234'}, 201)
            client.post.side_effect = post
            args = ('https://example.invalid', TOKEN, 'a'*24, 'order-1', str(Path(temp)/'orders.sqlite'))
            worker = threading.Thread(target=lambda: results.append(issue_once(*args, session=client)))
            worker.start()
            self.assertTrue(entered.wait(5))
            try:
                with self.assertRaises(OrderNeedsAttention):
                    issue_once(*args, session=client)
            finally:
                release.set()
                worker.join(5)
            self.assertEqual(1, client.post.call_count)
            self.assertEqual(1, len(results))

if __name__ == '__main__':
    unittest.main()
