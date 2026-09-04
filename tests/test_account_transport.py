import base64
import datetime
import json
import time
import unittest
from unittest.mock import patch

import jwt
from account_transport import HeadlessServerHandler
from bcsfe_runtime import core, scoped_runtime


class Response:
    def __init__(self, payload=None, status=200):
        self.payload = payload if payload is not None else {'statusCode': 0}
        self.status_code = status
        self.headers = {'content-type': 'application/json'}
        self.content = json.dumps(self.payload).encode()
        self.reason = 'synthetic response'
    def json(self):
        return self.payload


class Transport:
    def __init__(self, sf, *, fail=None, include_account_code=False):
        self.sf, self.fail = sf, fail
        self.include_account_code = include_account_code
        self.calls = []
    def factory(self, url, headers=None, data=None, form=None):
        transport = self
        class Request:
            def send(self, method, no_timeout=False):
                body = json.loads(data.to_str()) if data is not None and data.data else None
                transport.calls.append({'method': method, 'url': url, 'body': body,
                                        'headers': headers, 'form': form, 'no_timeout': no_timeout})
                if url.startswith(core.ServerHandler.backups_url):
                    if transport.fail == 'allocate':
                        return None
                    return Response({'accountId': 'new-account'})
                if url.endswith('/v1/user/password'):
                    return Response()
                if url.endswith('/v1/users'):
                    if transport.fail == 'password':
                        return Response()
                    payload = {'password': 'test-password', 'passwordRefreshToken': 'test-refresh'}
                    if transport.include_account_code:
                        payload['accountCode'] = transport.sf.inquiry_code
                    return Response({'statusCode': 1, 'timestamp': 1700000000, 'payload': payload})
                if url.endswith('/v1/tokens'):
                    if transport.fail == 'token':
                        return Response()
                    token = jwt.encode({'accountCode': transport.sf.inquiry_code, 'exp': int(time.time()) + 3600},
                                       'synthetic-secret-for-offline-tests-only', algorithm='HS256')
                    return Response({'statusCode': 1, 'payload': {'token': token}})
                if '/v2/save/key?' in url:
                    if transport.fail == 'key':
                        return Response()
                    return Response({'statusCode': 1, 'payload': {
                        'url': 'https://fixture.invalid/upload', 'key': 'save/kr/' + transport.sf.inquiry_code,
                        'policy': base64.b64encode(json.dumps({'expiration':'2099-01-01T00:00:00.000Z'}).encode()).decode()}})
                if url.endswith('/v1/managed-items'):
                    return Response({'statusCode': 0 if transport.fail == 'sync' else 1})
                if url == 'https://fixture.invalid/upload':
                    if transport.fail == 'aws_timeout':
                        return None
                    return Response(status=204)
                if url.endswith('/v2/transfers'):
                    if transport.fail == 'codes':
                        return Response()
                    return Response({'statusCode': 1, 'payload': {'transferCode': 'issued-transfer', 'pin': '1234'}})
                if url.endswith('/v2/backups'):
                    return Response({'statusCode': 1})
                raise AssertionError('Unexpected transport URL: ' + url)
            def get(self, **kwargs):
                return self.send('GET', **kwargs)
            def post(self, **kwargs):
                return self.send('POST', **kwargs)
        return Request()
    def count(self, suffix):
        return sum(call['url'].endswith(suffix) for call in self.calls)


class AccountTransportTests(unittest.TestCase):
    def setUp(self):
        self.runtime = scoped_runtime()
        self.runtime.__enter__()
        self.addCleanup(lambda: self.runtime.__exit__(None, None, None))
        self.network = patch('socket.create_connection', side_effect=AssertionError('No live network'))
        self.network.start(); self.addCleanup(self.network.stop)
        self.logger = patch.object(core.ServerHandler, 'log_error')
        self.logger.start(); self.addCleanup(self.logger.stop)
        self.sf = core.SaveFile(cc=core.CountryCode.from_code('kr'), gv=core.GameVersion(150500), load=False)
        for field in ('date','date_2','date_3','date_4'):
            setattr(self.sf, field, datetime.datetime(2024,1,2))
        self.sf.inquiry_code = 'original-account'
        self.sf.xp = 9876
        self.sf.catfood = 321
        self.sf.officer_pass.play_time = 123456
        self.sf.lineups.slots[0].slots[0].cat_id = 2
        self.handler = HeadlessServerHandler(self.sf, print=False)
    def transport(self, **kwargs):
        transport = Transport(self.sf, **kwargs)
        patcher = patch.object(core, 'RequestHandler', side_effect=transport.factory)
        patcher.start(); self.addCleanup(patcher.stop)
        return transport
    def test_auth_failure_does_not_allocate_an_account(self):
        transport = self.transport(fail='password')
        self.assertIsNone(self.handler.get_codes(tries=100))
        self.assertEqual(self.sf.inquiry_code, 'original-account')
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(transport.count('/v1/user/password'), 1)
        self.assertEqual(transport.count('/v1/users'), 1)
        self.assertFalse(any(call['url'].startswith(core.ServerHandler.backups_url) for call in transport.calls))
    def test_original_hidden_creation_is_not_bounded_by_outer_tries(self):
        original = core.ServerHandler(self.sf, print=False)
        allocations = []
        def allocate():
            allocations.append(True)
            if len(allocations) == 3:
                raise RuntimeError('Stop synthetic recursion')
            return 'allocated-' + str(len(allocations))
        with patch.object(original, 'refresh_password', return_value=None), \
             patch.object(original, 'get_password_new', return_value=None), \
             patch.object(original, 'get_new_inquiry_code', side_effect=allocate):
            with self.assertRaisesRegex(RuntimeError, 'synthetic recursion'):
                original.get_codes(tries=1)
        self.assertEqual(len(allocations), 3)
    def test_explicit_account_creation_uses_original_protocol(self):
        transport = self.transport()
        self.assertTrue(self.handler.create_new_account(tries=99))
        self.assertEqual([call['method'] for call in transport.calls], ['GET','POST','POST','POST','GET','POST'])
        self.assertEqual(transport.calls[0]['url'], core.ServerHandler.backups_url + '/?action=createAccount&referenceId=')
        self.assertEqual(transport.calls[1]['body']['accountCode'], 'new-account')
        self.assertIn('EXPECT_THIS_TO_FAIL', transport.calls[1]['body']['passwordRefreshToken'])
        self.assertEqual(transport.calls[2]['body']['accountCode'], 'new-account')
        self.assertEqual(transport.calls[3]['body']['clientInfo']['client'], {'countryCode':'kr','version':150500})
        sync = transport.calls[-1]['body']
        self.assertEqual((sync['catfoodAmount'], sync['isPaid']), (321, True))
        self.assertEqual(self.handler.get_stored_password(), 'test-password')
        self.assertEqual(self.sf.password_refresh_token, 'test-refresh')
        raw = self.sf.to_data().data
        parsed = core.SaveFile(core.Data(raw))
        self.assertTrue(parsed.verify_hash()); self.assertEqual(parsed.to_data().data, raw)
        self.assertEqual((parsed.xp, parsed.officer_pass.play_time, parsed.lineups.slots[0].slots[0].cat_id), (9876,123456,2))
    def test_creation_stops_after_first_failed_stage(self):
        for failure, expected in (('allocate',1),('password',3),('token',4),('key',5),('sync',6)):
            with self.subTest(failure=failure):
                sf = core.SaveFile(core.Data(self.sf.to_data().data))
                sf.inquiry_code = 'source-' + failure
                handler = HeadlessServerHandler(sf, print=False)
                transport = Transport(sf, fail=failure)
                with patch.object(core, 'RequestHandler', side_effect=transport.factory):
                    self.assertFalse(handler.create_new_account(tries=10))
                self.assertEqual(len(transport.calls), expected)
                self.assertEqual(sum(call['url'].startswith(core.ServerHandler.backups_url) for call in transport.calls),1)
                self.assertEqual(sf.inquiry_code, 'source-allocate' if failure == 'allocate' else 'new-account')
    def test_bad_cached_token_is_replaced_once(self):
        transport = self.transport()
        self.handler.save_password('known-password')
        self.handler.save_auth_token('malformed-jwt')
        self.assertIsNotNone(self.handler.get_auth_token(tries=10))
        self.assertEqual(transport.count('/v1/tokens'), 1)
        self.assertEqual(len(transport.calls),1)
    def test_failed_auth_token_is_not_retried(self):
        transport = self.transport(fail='token')
        self.handler.save_password('known-password')
        self.assertIsNone(self.handler.get_auth_token(tries=99))
        self.assertEqual(transport.count('/v1/tokens'),1)
        self.assertEqual(len(transport.calls),1)
    def test_password_payload_account_identity_and_timestamp_preserved(self):
        transport = self.transport(include_account_code=True)
        self.assertTrue(self.handler.create_new_account())
        self.assertEqual(self.sf.energy_penalty_timestamp,1700000000)
        self.assertEqual(self.sf.inquiry_code,'new-account')
        self.assertEqual(transport.count('/v1/users'),1)
        self.assertEqual(transport.count('/v1/tokens'),1)
    def test_failed_transfer_issuance_has_no_second_attempt(self):
        transport = self.transport(fail='codes')
        self.handler.save_password('known-password')
        self.assertIsNone(self.handler.get_codes(tries=50))
        self.assertEqual(transport.count('/v2/transfers'),1)
        uploads = [call for call in transport.calls if call['url']=='https://fixture.invalid/upload']
        self.assertEqual(len(uploads),1)
        self.assertFalse(uploads[0]['no_timeout'])
        raw = uploads[0]['form'].data['file'].content
        self.assertTrue(core.SaveFile(core.Data(raw)).verify_hash())
    def test_successful_transfer_preserves_original_metadata_protocol(self):
        transport = self.transport()
        self.handler.save_password('known-password')
        self.assertEqual(self.handler.get_codes(), ('issued-transfer','1234'))
        issued = next(call for call in transport.calls if call['url'].endswith('/v2/transfers'))
        self.assertEqual(issued['body']['playTime'],123456)
        self.assertEqual(issued['body']['saveKey'],'save/kr/original-account')
        self.assertIn('signature_v1',issued['body'])
        self.assertTrue(issued['headers']['authorization'].startswith('Bearer '))
        self.assertEqual(self.sf.inquiry_code,'original-account')
    def test_aws_timeout_returns_without_issuing_codes(self):
        transport = self.transport(fail='aws_timeout')
        self.handler.save_password('known-password')
        self.assertIsNone(self.handler.get_codes())
        self.assertEqual(transport.count('/v2/transfers'),0)
        upload = next(call for call in transport.calls if call['url']=='https://fixture.invalid/upload')
        self.assertFalse(upload['no_timeout'])
    def test_zero_attempts_do_not_contact_upstream(self):
        transport = self.transport()
        self.assertFalse(self.handler.create_new_account(tries=0))
        self.assertIsNone(self.handler.get_codes(tries=0))
        self.assertEqual(transport.calls,[])


if __name__ == '__main__':
    unittest.main()
