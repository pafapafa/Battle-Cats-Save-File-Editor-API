"""HTTP behavior, binary persistence, transport failures and backup recovery."""
import base64
import copy
import datetime
import os
import unittest
from contextlib import contextmanager
from types import SimpleNamespace as NS
from unittest.mock import patch
from bcsfe_runtime import core
from main import app
import editor_api
import editor_engine
import test_editor_integration as integration

TOKEN='offline-editor-test-'+('x'*40)

class FakeHandler:
    account_ok=True
    sync_ok=True
    items_ok=True
    codes=('new-transfer','1234')
    raise_method=None
    calls=[]
    def __init__(self,sf):self.sf=sf
    def call(self,name):
        self.calls.append(name)
        if self.raise_method==name:raise ConnectionError('private-upstream-detail')
    def create_new_account(self,tries=1):
        self.call('new')
        if self.account_ok:self.sf.inquiry_code='created-account'
        return self.account_ok and self.update_managed_items()
    def update_managed_items(self):self.call('sync');return self.sync_ok
    def upload_meta_data(self):self.call('items');return self.items_ok
    def get_codes(self,tries=1):self.call('upload');return self.codes
    def save_password(self,value):self.call('password')

class EditorHTTPTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'EDITOR_API_KEY':TOKEN})
        self.env.start();self.addCleanup(self.env.stop)
        app.testing=True
        app.config['EDITOR_HANDLER_FACTORY']=FakeHandler
        app.config.pop('EDITOR_RECEIVE_FACTORY',None)
        self.addCleanup(lambda:app.config.pop('EDITOR_HANDLER_FACTORY',None))
        self.addCleanup(lambda:app.config.pop('EDITOR_RECEIVE_FACTORY',None))
        FakeHandler.account_ok=FakeHandler.sync_ok=FakeHandler.items_ok=True
        FakeHandler.codes=('new-transfer','1234');FakeHandler.raise_method=None;FakeHandler.calls=[]
        self.client=app.test_client()
        self.headers={'Authorization':'Bearer '+TOKEN}
        sf=core.SaveFile(cc=core.CountryCode.from_code('kr'),gv=core.GameVersion(150500),load=False)
        for f in ('date','date_2','date_3','date_4'):setattr(sf,f,datetime.datetime(2024,1,2))
        sf.xp=1234;sf.catfood=234;sf.inquiry_code='source-account'
        sf.officer_pass.play_time=6543;sf.gamatoto.skin=1
        sf.lineups.slots[0].slots[0].cat_id=2
        sf.missions.clear_states={7:2};sf.missions.requirements={7:8}
        self.raw=sf.to_data().data
        self.payload={'save_base64':base64.b64encode(self.raw).decode(),'country_code':'kr'}
    def post(self,path,data=None):
        return self.client.post(path,json=self.payload if data is None else data,headers=self.headers)
    def test_xp_edit_only_and_original_backup(self):
        response=self.post('/v2/save/edit',{**self.payload,'operations':[{'action':'items.xp','args':{'value':4321}}]})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['changes'],[{'path':'/xp','before':1234,'after':4321}])
        self.assertEqual(base64.b64decode(response.json['backup_base64']),self.raw)
        result=core.SaveFile(core.Data(base64.b64decode(response.json['save_base64'])))
        self.assertEqual(result.xp,4321);self.assertEqual(result.officer_pass.play_time,6543)
        self.assertEqual(result.lineups.slots[0].slots[0].cat_id,2)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
    def test_file_output_and_download(self):
        response=self.post('/v2/save/edit',{**self.payload,'output':'file','operations':[{'action':'items.xp','args':{'value':0}}]})
        self.assertEqual(response.status_code,200)
        self.assertEqual(core.SaveFile(core.Data(response.data)).xp,0)
        self.assertEqual(self.post('/v2/save/download').data,self.raw)
    def test_json_roundtrip_with_numeric_keys_and_infinity(self):
        sf=core.SaveFile(core.Data(self.raw))
        sf.battle_items.items[0].endless_item.set_duration_mins(float('inf'),0)
        raw=sf.to_data().data
        exported=self.post('/v2/save/export',{'save_base64':base64.b64encode(raw).decode(),'country_code':'kr'})
        self.assertEqual(exported.status_code,200,exported.json)
        imported=self.post('/v2/save/import',{'state':exported.json['state']})
        self.assertEqual(imported.status_code,200,imported.json)
        self.assertEqual(base64.b64decode(imported.json['save_base64']),raw)
    def test_nonfinite_numeric_fields_do_not_corrupt_literal_strings(self):
        for text in ('Infinity','-Infinity','NaN'):
            with self.subTest(text=text):
                sf=core.SaveFile(core.Data(self.raw))
                sf.inquiry_code=text;sf.password_refresh_token=text
                sf.battle_items.items[0].endless_item.end=float(text)
                sf.ud1=float(text)
                raw=sf.to_data().data
                state=self.post('/v2/save/export',{'save_base64':base64.b64encode(raw).decode(),'country_code':'kr'}).json['state']
                response=self.post('/v2/save/import',{'state':state})
                self.assertEqual(response.status_code,200,response.json)
                self.assertEqual(base64.b64decode(response.json['save_base64']),raw)
    def test_app_preserves_private_get_no_store(self):
        response=self.client.get('/v2/editor/config',headers=self.headers)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
    def test_json_unknown_fields_cannot_silently_disappear(self):
        state=self.post('/v2/save/export').json['state'];state['typo_xp']=999
        response=self.post('/v2/save/import',{'state':state})
        self.assertEqual(response.status_code,422,response.json)
    def test_invalid_inputs_never_succeed(self):
        for value in (True,1.0,'1',-1,2147483648,None):
            with self.subTest(value=value):
                r=self.post('/v2/save/edit',{**self.payload,'operations':[{'action':'items.xp','args':{'value':value}}]})
                self.assertEqual(r.status_code,422,r.json)
        r=self.post('/v2/save/edit',{**self.payload,'operations':[{'action':'not-real'}]})
        self.assertEqual(r.status_code,422)
        r=self.post('/v2/save/inspect',{'save_base64':'%%%','country_code':'kr'})
        self.assertEqual(r.status_code,400)
    def test_late_failure_does_not_return_partial_save(self):
        r=self.post('/v2/save/edit',{**self.payload,'operations':[{'action':'items.xp','args':{'value':4321}},
          {'action':'items.catamins','args':{'values':{'9999':2}}}]})
        self.assertEqual(r.status_code,422,r.json)
        self.assertFalse(r.json['applied']);self.assertNotIn('save_base64',r.json)
        self.assertEqual(self.post('/v2/save/inspect').json['state']['xp'],1234)
    def test_auth_and_public_information(self):
        for path in ('/v2/save/inspect','/edit','/info'):
            self.assertEqual(self.client.post(path,json=self.payload).status_code,401)
        for path in ('/','/docs','/openapi.json','/v2/features','/v2/capabilities'):
            with self.subTest(path=path):
                r=self.client.get(path);self.assertEqual(r.status_code,200,r.get_data(as_text=True)[:300])
                self.assertNotIn(TOKEN,r.get_data(as_text=True))
        self.assertEqual(self.client.get('/v2/editor/config',headers=self.headers).status_code,200)
    def test_account_unknown_fields_rejected_before_remote_call(self):
        r=self.post('/v2/account/new',{**self.payload,'xp':99999})
        self.assertEqual(r.status_code,400,r.json)
        self.assertEqual(FakeHandler.calls,[])
    def test_openapi_includes_every_action_argument_schema(self):
        schema=self.client.get('/openapi.json').json['components']['schemas']['EditorOperation']
        self.assertEqual({entry['properties']['action']['const'] for entry in schema['oneOf']},set(editor_engine.ACTIONS))
        from jsonschema import Draft202012Validator
        validator=Draft202012Validator(schema)
        self.assertFalse(list(validator.iter_errors({'action':'items.xp','args':{'value':10}})))
        self.assertTrue(list(validator.iter_errors({'action':'items.xp','args':{'value':'10'}})))
    def test_remote_false_results_are_failures_with_backups(self):
        cases=[('/v2/account/new','account_ok',False),('/v2/account/new','sync_ok',False),
               ('/v2/account/upload-items','items_ok',False),('/v2/save/upload','codes',None),
               ('/v2/save/upload','codes',('onlyone',))]
        for path,field,value in cases:
            with self.subTest(path=path,field=field),patch.object(FakeHandler,field,value):
                r=self.post(path);self.assertEqual(r.status_code,502,r.json)
                self.assertFalse(r.json['retry_safe']);self.assertEqual(base64.b64decode(r.json['backup_base64']),self.raw)
                self.assertIn('save_base64',r.json)
    def test_remote_exceptions_keep_recovery_and_hide_upstream_details(self):
        for path,method in (('/v2/account/new','sync'),('/v2/account/upload-items','items'),('/v2/save/upload','upload')):
            with self.subTest(path=path),patch.object(FakeHandler,'raise_method',method):
                r=self.post(path);self.assertEqual(r.status_code,502,r.json)
                self.assertEqual(base64.b64decode(r.json['backup_base64']),self.raw)
                self.assertIn('save_base64',r.json)
                self.assertNotIn('private-upstream-detail',r.get_data(as_text=True))
    def test_new_account_checks_distinct_identity_and_serializes(self):
        r=self.post('/v2/account/new');self.assertEqual(r.status_code,200,r.json)
        sf=core.SaveFile(core.Data(base64.b64decode(r.json['save_base64'])))
        self.assertEqual(sf.inquiry_code,'created-account');self.assertEqual(sf.xp,1234)
        self.assertEqual(FakeHandler.calls,['new','sync'])
        with patch.object(FakeHandler,'create_new_account',return_value=True):
            self.assertEqual(self.post('/v2/account/new').status_code,502)
    def test_region_conversion_and_items_upload(self):
        r=self.post('/v2/account/convert-region',{**self.payload,'target_country_code':'en'})
        self.assertEqual(r.status_code,200,r.json)
        sf=core.SaveFile(core.Data(base64.b64decode(r.json['save_base64'])))
        self.assertEqual(sf.cc.get_code(),'en');self.assertEqual(sf.xp,1234)
        self.assertEqual(self.post('/v2/account/upload-items').status_code,200)
    def receive(self,raw):
        return NS(content=raw,status_code=200,headers={'content-type':'application/octet-stream','Nyanko-Password-Refresh-Token':'new-refresh','Nyanko-Password':'new-password'})
    def test_transfer_received_raw_and_new_credentials_are_preserved(self):
        app.config['EDITOR_RECEIVE_FACTORY']=lambda url,data:self.receive(self.raw)
        r=self.post('/v2/save/from-transfer',{'transfer_code':'abc','confirmation_code':'1234','country_code':'kr'})
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(base64.b64decode(r.json['backup_base64']),self.raw)
        sf=core.SaveFile(core.Data(base64.b64decode(r.json['save_base64'])))
        self.assertEqual(sf.password_refresh_token,'new-refresh')
        self.assertEqual(FakeHandler.calls,['password'])
    def test_transfer_parse_failure_returns_received_bytes(self):
        app.config['EDITOR_RECEIVE_FACTORY']=lambda url,data:self.receive(b'unsupported-save-bytes'*4)
        r=self.post('/v2/save/from-transfer',{'transfer_code':'abc','confirmation_code':'1234'})
        self.assertEqual(r.status_code,422,r.json)
        self.assertEqual(base64.b64decode(r.json['backup_base64']),b'unsupported-save-bytes'*4)
    def test_legacy_exception_after_reception_returns_recovery(self):
        app.config['EDITOR_RECEIVE_FACTORY']=lambda *args:self.receive(self.raw)
        for endpoint in ('/info','/edit'):
            with self.subTest(endpoint=endpoint),patch.object(FakeHandler,'raise_method','password'):
                r=self.post(endpoint,{'tc':'abc','cc':'1234',**({'xp':0} if endpoint=='/edit' else {})})
                self.assertEqual(r.status_code,502,r.json)
                self.assertEqual(base64.b64decode(r.json['backup_base64']),self.raw)
                self.assertFalse(r.json['retry_safe'])

    def test_legacy_rejects_bad_payload_before_consuming_transfer(self):
        called=[];app.config['EDITOR_RECEIVE_FACTORY']=lambda *args:called.append(args)
        r=self.post('/edit',{'tc':'abc','cc':'1234','catamins':True})
        self.assertEqual(r.status_code,422,r.json);self.assertEqual(called,[])
    def test_legacy_success_and_failed_upload_preserve_only_requested_edit(self):
        app.config['EDITOR_RECEIVE_FACTORY']=lambda *args:self.receive(self.raw)
        data={'tc':'abc','cc':'1234','country':'kr','xp':0}
        r=self.post('/edit',data);self.assertEqual(r.status_code,200,r.json)
        self.assertEqual([d['path'] for d in r.json['changes']],['/xp'])
        with patch.object(FakeHandler,'codes',None):
            r=self.post('/edit',data);self.assertEqual(r.status_code,502,r.json)
            self.assertEqual(core.SaveFile(core.Data(base64.b64decode(r.json['save_base64']))).xp,0)
    def test_all_action_payloads_through_http_with_fixture_metadata(self):
        fixture=integration.EditorIntegrationTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        @contextmanager
        def existing_runtime():yield core.core_data
        with patch.object(editor_api,'scoped_runtime',existing_runtime):
            for action,args in integration.CASES.items():
                with self.subTest(action=action):
                    raw=fixture.raw
                    if action=='stages.unlock_aku':
                        from bcsfe.core.game.map import event
                        sf=core.SaveFile(core.Data(raw))
                        for group in sf.event_stages.chapters:
                            group.chapters=[event.EventSubChapterStars([event.EventSubChapter.init(5) for _ in range(3)]) for _ in range(269)]
                        raw=sf.to_data().data
                    r=self.post('/v2/save/edit',{'save_base64':base64.b64encode(raw).decode(),'country_code':'kr',
                                  'operations':[{'action':action,'args':args}]})
                    self.assertEqual(r.status_code,200,r.json)
                    self.assertGreater(r.json['change_count'],0)
                    self.assertEqual(base64.b64decode(r.json['backup_base64']),raw)

if __name__=='__main__':unittest.main()
