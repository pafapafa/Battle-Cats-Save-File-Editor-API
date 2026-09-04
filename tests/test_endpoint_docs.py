"""Endpoint documentation must track real routes, payloads and response formats."""
import copy
import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from main import app, OPENAPI_SPEC
import editor_metadata
import test_editor_api as http_fixtures
from test_editor_api import FakeHandler


class EndpointDocsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = http_fixtures.EditorHTTPTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.headers = self.fixture.headers
        self.catalog = json.loads((Path(__file__).resolve().parents[1] / 'static' / 'endpoint-docs.json').read_text(encoding='utf-8'))
        self.spec = OPENAPI_SPEC

    def validator(self, schema):
        return Draft202012Validator({'components': self.spec['components'], 'allOf': [schema]})

    def documented_response(self, path, method, response):
        self.assertIn(str(response.status_code), self.spec['paths'][path][method]['responses'], (path, response.status_code, response.get_json(silent=True)))
        content = self.spec['paths'][path][method]['responses'][str(response.status_code)]['content']
        self.assertIn(response.mimetype, content, path)
        schema = content[response.mimetype]['schema']
        if response.is_json:
            self.validator(schema).validate(response.get_json())
        elif response.mimetype == 'application/octet-stream':
            self.assertEqual({'type': 'string', 'format': 'binary'}, schema)
            self.assertTrue(response.headers['Content-Disposition'].startswith('attachment;'))
        else:
            self.validator(schema).validate(response.get_data(as_text=True))
        return response

    def test_every_explicit_route_has_one_catalog_entry_and_complete_openapi(self):
        routes = {method + ' ' + re.sub(r'<(?:[^:>]+:)?([^>]+)>', r'{\1}', rule.rule)
                  for rule in app.url_map.iter_rules() if rule.endpoint != 'static'
                  for method in rule.methods - {'HEAD', 'OPTIONS'}}
        documented = {method.upper() + ' ' + path for path, methods in self.spec['paths'].items() for method in methods}
        self.assertEqual(routes, documented)
        self.assertEqual(routes, set(self.catalog['endpoints']))
        categories = {item['id'] for item in self.catalog['categories']}
        for key, entry in self.catalog['endpoints'].items():
            with self.subTest(endpoint=key):
                method, path = key.split(' ', 1)
                operation = self.spec['paths'][path][method.lower()]
                self.assertIn(entry['category'], categories)
                self.assertTrue(entry['description'])
                self.assertTrue(operation.get('description'))
                self.assertTrue(operation.get('summary'))
                self.assertIn('security', operation)
                for response in operation['responses'].values():
                    self.assertTrue(response.get('content'))
                    for media in response['content'].values():
                        self.assertIn('schema', media)
        for schema in self.spec['components']['schemas'].values():
            Draft202012Validator.check_schema(schema)

    def test_synthetic_request_response_and_query_examples_match_schemas(self):
        for key, entry in self.catalog['endpoints'].items():
            method, path = key.split(' ', 1)
            operation = self.spec['paths'][path][method.lower()]
            with self.subTest(endpoint=key):
                if 'example' in entry:
                    schema = operation['requestBody']['content']['application/json']['schema']
                    self.validator(schema).validate(entry['example'])
                if 'response_example' in entry and not isinstance(entry['response_example'], str):
                    success = operation['responses'].get('201', operation['responses'].get('200'))
                    self.validator(success['content']['application/json']['schema']).validate(entry['response_example'])
                for name, value in entry.get('query_example', {}).items():
                    parameter = next(p for p in operation['parameters'] if p['in'] == 'query' and p['name'] == name)
                    self.validator(parameter['schema']).validate(value)

    def test_actual_public_file_and_edit_responses_match_contracts(self):
        for path in ('/', '/docs', '/openapi.json', '/v2/features', '/v2/capabilities'):
            with self.subTest(path=path):
                self.documented_response(path, 'get', self.client.get(path))
        for path in ('/v2/save/inspect', '/v2/save/export', '/v2/save/download'):
            with self.subTest(path=path):
                self.documented_response(path, 'post', self.fixture.post(path))
        state = self.fixture.post('/v2/save/export').json['state']
        self.documented_response('/v2/save/import', 'post', self.fixture.post('/v2/save/import', {'state': state}))
        for output in ('json', 'file'):
            with self.subTest(output=output):
                data = {**self.fixture.payload, 'operations': [{'action': 'items.xp', 'args': {'value': 4321}}], 'output': output}
                self.documented_response('/v2/save/edit', 'post', self.fixture.post('/v2/save/edit', data))

    def test_actual_account_and_legacy_success_and_recovery_responses(self):
        app.config['EDITOR_RECEIVE_FACTORY'] = lambda *args: self.fixture.receive(self.fixture.raw)
        for path, payload in [
            ('/v2/save/from-transfer', {'transfer_code': 'SOURCE123', 'confirmation_code': '1234'}),
            ('/v2/save/upload', self.fixture.payload),
            ('/v2/account/new', self.fixture.payload),
            ('/v2/account/upload-items', self.fixture.payload),
            ('/v2/account/convert-region', {**self.fixture.payload, 'target_country_code': 'en'}),
            ('/info', {'tc': 'SOURCE123', 'cc': '1234'}),
            ('/edit', {'tc': 'SOURCE123', 'cc': '1234', 'xp': 4321}),
        ]:
            with self.subTest(path=path):
                response = self.fixture.post(path, payload)
                self.assertEqual(200, response.status_code, response.json)
                self.documented_response(path, 'post', response)
        with patch.object(FakeHandler, 'codes', None):
            for path, payload in [('/v2/save/upload', self.fixture.payload), ('/edit', {'tc': 'SOURCE123', 'cc': '1234', 'xp': 4321})]:
                response = self.fixture.post(path, payload)
                self.assertEqual(502, response.status_code)
                self.documented_response(path, 'post', response)
                self.assertFalse(response.json['retry_safe'])

    def test_metadata_contracts_use_actual_return_fields_and_nullable_delete_version(self):
        prepared = {'country_code': 'kr', 'requested_version': '15.5.0', 'resolved_version': '15.4.0',
                    'exact_match': False, 'downloaded': True, 'source': 'https://example.invalid/index.json', 'archive_source': 'https://example.invalid/archive.zip'}
        deleted = {'country_code': 'kr', 'deleted_versions': ['15.4.0'], 'skipped_entries': 1}
        with patch.object(editor_metadata, 'metadata_versions', return_value={'kr': ['15.4.0']}), \
             patch.object(editor_metadata, 'prepare_metadata', return_value=prepared), \
             patch.object(editor_metadata, 'delete_metadata', return_value=deleted) as clear:
            self.documented_response('/v2/metadata/versions', 'get', self.client.get('/v2/metadata/versions', headers=self.headers))
            self.documented_response('/v2/metadata/prepare', 'post', self.fixture.post('/v2/metadata/prepare', {'country_code': 'kr', 'game_version': 150500}))
            payload = {'country_code': 'kr', 'game_version': None}
            schema = self.spec['paths']['/v2/metadata/cache']['delete']['requestBody']['content']['application/json']['schema']
            self.validator(schema).validate(payload)
            response = self.client.delete('/v2/metadata/cache', json=payload, headers=self.headers)
            self.documented_response('/v2/metadata/cache', 'delete', response)
            clear.assert_called_once_with('kr', None)
        self.documented_response('/v2/editor/config', 'get', self.client.get('/v2/editor/config', headers=self.headers))
        prepare_schema = self.spec['paths']['/v2/metadata/prepare']['post']['requestBody']['content']['application/json']['schema']
        self.assertFalse(self.validator(prepare_schema).is_valid({'country_code': 'kr'}))
        self.assertNotIn('default', prepare_schema['properties']['country_code'])


if __name__ == '__main__':
    unittest.main()
