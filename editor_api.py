"""File-first HTTP interface for the complete typed editor."""
from __future__ import annotations
import base64
import copy
import hashlib
import hmac
import io
import json
import re
from functools import wraps
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, send_file
from werkzeug.exceptions import HTTPException
from bcsfe_runtime import core, scoped_runtime
from editor_engine import (ACTIONS, EditError, apply_operations, comparable, public_catalog,
                           serialize_checked, to_state, validate_operations, changes, StrictValidator)
from template_store import setting

bp=Blueprint('editor',__name__,url_prefix='/v2')
MAX_SAVE=1024*1024

class APIProblem(Exception):
    def __init__(self,message,status=400,**details):
        self.message,self.status,self.details=message,status,details

def body():
    value=request.get_json(silent=True)
    if not isinstance(value,dict):
        raise APIProblem('Provide a JSON object.')
    fields = {
        '/v2/save/edit': {'save_base64','country_code','operations','output'},
        '/v2/save/import': {'state'},
        '/v2/save/from-transfer': {'transfer_code','confirmation_code','country_code','game_version'},
        '/v2/metadata/prepare': {'country_code','game_version'},
        '/v2/metadata/cache': {'country_code','game_version'},
        '/v2/account/convert-region': {'save_base64','country_code','target_country_code'},
    }
    allowed = fields.get(request.path, {'save_base64','country_code'} if request.path.startswith(('/v2/save/','/v2/account/')) else None)
    if allowed is not None and set(value)-allowed:
        raise APIProblem('Unknown request fields: '+', '.join(sorted(set(value)-allowed)))
    return value

def b64(raw):
    return base64.b64encode(raw).decode('ascii')

def input_save(data):
    value=data.get('save_base64')
    if not isinstance(value,str) or len(value)>(MAX_SAVE+2)//3*4:
        raise APIProblem('Provide save_base64 for a raw save of at most 1 MiB.')
    try:
        raw=base64.b64decode(value,validate=True)
    except ValueError:
        raise APIProblem('Invalid save_base64.') from None
    country=data.get('country_code','kr')
    if country not in ('kr','en','jp','tw') or not 32<=len(raw)<=MAX_SAVE:
        raise APIProblem('Invalid save size or country_code.')
    try:
        sf=core.SaveFile(core.Data(raw),cc=core.CountryCode.from_code(country))
        if not sf.verify_hash() or sf.cc.get_code()!=country:
            raise ValueError('Hash or country mismatch')
    except Exception:
        raise APIProblem('Save cannot be parsed or its checksum/region is invalid.',422) from None
    g.editor_original, g.editor_save = raw, sf
    return raw,sf

def file_metadata(raw,sf):
    return {'country_code':sf.cc.get_code(),'game_version':sf.game_version.game_version,
            'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def handler(sf):
    factory=current_app.config.get('EDITOR_HANDLER_FACTORY')
    from account_transport import HeadlessServerHandler
    return factory(sf) if factory else HeadlessServerHandler(sf,print=False)

def confirmed_codes(value):
    return isinstance(value,(tuple,list)) and len(value)==2 and all(isinstance(v,str) and v for v in value)

def remote_recovery(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        try:
            return function(*args,**kwargs)
        except Exception as exc:
            if isinstance(exc,(EditError,ValueError)) and not hasattr(g,'editor_original'):
                raise
            if isinstance(exc,HTTPException):
                raise
            if isinstance(exc,APIProblem):
                problem=exc
            else:
                problem=APIProblem('Remote operation did not complete ('+type(exc).__name__+').',502)
            problem.details.setdefault('retry_safe',False)
            original=getattr(g,'editor_original',None)
            sf=getattr(g,'editor_save',None)
            if original is not None:
                problem.details.setdefault('backup_base64',b64(original))
                recovery=original
                if sf is not None:
                    try:
                        recovery=sf.to_data().data
                    except Exception:
                        pass
                problem.details.setdefault('save_base64',b64(recovery))
            raise problem from None
    return wrapped


@bp.before_request
def auth():
    if request.method=='OPTIONS' or (request.method=='GET' and request.path in ('/v2/features','/v2/capabilities')):
        return
    key=setting('EDITOR_API_KEY') or setting('TEMPLATE_API_KEY')
    if len(key)<32:
        raise APIProblem('Configure EDITOR_API_KEY or TEMPLATE_API_KEY.',503)
    supplied=request.headers.get('Authorization','')
    if not hmac.compare_digest(supplied.encode(),('Bearer '+key).encode()):
        raise APIProblem('A valid editor Bearer token is required.',401)

@bp.after_request
def headers(response):
    response.headers['Cache-Control']='no-store'
    return response

@bp.errorhandler(APIProblem)
def problem(exc):
    return jsonify(success=False,message=exc.message,**exc.details),exc.status

@bp.errorhandler(EditError)
def edit_error(exc):
    return jsonify(success=False,message=str(exc),applied=False),422

@bp.errorhandler(ValueError)
def invalid(exc):
    return jsonify(success=False,message=str(exc)),422

@bp.errorhandler(Exception)
def unexpected(exc):
    if isinstance(exc,HTTPException):
        return jsonify(success=False,message=exc.description),exc.code
    return jsonify(success=False,message='Editor operation failed ('+type(exc).__name__+').'),500

@bp.get('/features')
def features():
    from editor_coverage import coverage
    return jsonify(success=True,reference='User-provided BCSFE 3.6.0 source',actions=public_catalog(),features=coverage())

@bp.get('/capabilities')
def capabilities():
    return jsonify(success=True,offline_editing=True,json_import_export=True,raw_download=True,
                   account_transport='implemented; actual account acceptance is not automatically guaranteed',
                   device_push={'available':False,'reason':'ADB/root require a companion running beside the device.'},
                   external_editor_themes={'available':False,'reason':'Terminal display customization is not used by the HTTP API.'})

@bp.post('/save/inspect')
def inspect():
    with scoped_runtime():
        raw,sf=input_save(body())
        response={'success':True,**file_metadata(raw,sf),'state':to_state(sf)}
    return jsonify(response)

@bp.post('/save/edit')
def edit():
    data=body()
    unknown=set(data)-{'save_base64','country_code','operations','output'}
    if unknown:
        raise APIProblem('Unknown request fields: '+', '.join(sorted(unknown)))
    operations=data.get('operations')
    validate_operations(operations)
    if data.get('output','json') not in ('json','file'):
        raise APIProblem('output must be json or file.')
    with scoped_runtime():
        original,sf=input_save(data)
        if sf.to_data().data!=original:
            raise APIProblem('Original save is not a stable binary round trip; editing was refused.',422)
        edited,raw,delta=apply_operations(sf,operations,isolate=False)
    if data.get('output')=='file':
        response=send_file(io.BytesIO(raw),mimetype='application/octet-stream',as_attachment=True,
                           download_name='edited.save',max_age=0)
        response.headers['X-Save-SHA256']=hashlib.sha256(raw).hexdigest()
        return response
    if data.get('output','json')!='json':
        raise APIProblem('output must be json or file.')
    return jsonify(success=True,applied=True,**file_metadata(raw,edited),
                   save_base64=b64(raw),backup_base64=b64(original),
                   changes=delta[:1000],change_count=len(delta),changes_truncated=len(delta)>1000)

@bp.post('/save/export')
def export_json():
    with scoped_runtime():
        raw,sf=input_save(body())
        return jsonify(success=True,**file_metadata(raw,sf),state=to_state(sf))

class JSONFloatLiteral(str):
    """Remain text for string fields; become a number only in float writers.

    The original struct.pack-based double writer calls __float__. This avoids
    interpreting an inquiry code or password named "Infinity" as a number.
    """
    def __float__(self):
        return float(str(self))

def restore_special_numbers(value):
    if isinstance(value,dict):
        return {k:restore_special_numbers(v) for k,v in value.items()}
    if isinstance(value,list):
        return [restore_special_numbers(v) for v in value]
    if isinstance(value,str) and value in ('Infinity','-Infinity','NaN'):
        return JSONFloatLiteral(value)
    return value

@bp.post('/save/import')
def import_json():
    data=body()
    state=data.get('state')
    if not isinstance(state,dict) or state.get('cc') not in ('kr','en','jp','tw') or type(state.get('game_version')) is not int:
        raise APIProblem('Provide a full BCSFE state object from /v2/save/export.')
    with scoped_runtime():
        try:
            sf=core.SaveFile.from_dict(restore_special_numbers(state),warn=False)
            if changes(state,to_state(sf)):
                raise EditError('JSON fields were not preserved by the original deserializer.')
            raw,parsed=serialize_checked(sf)
        except Exception as exc:
            raise APIProblem('JSON state cannot be saved without data loss ('+type(exc).__name__+').',422) from None
    if len(raw)>MAX_SAVE:
        raise APIProblem('Imported save is too large.',413)
    return jsonify(success=True,save_base64=b64(raw),**file_metadata(raw,parsed))

@bp.post('/save/download')
def download():
    with scoped_runtime():
        raw,_=input_save(body())
    return send_file(io.BytesIO(raw),mimetype='application/octet-stream',as_attachment=True,
                     download_name='backup.save',max_age=0)

def receive_transfer(transfer_code,pin,country='kr',game_version=150500):
    if not isinstance(transfer_code,str) or not re.fullmatch(r'[A-Za-z0-9]{1,64}',transfer_code):
        raise APIProblem('Invalid transfer_code.')
    if not isinstance(pin,str) or not re.fullmatch(r'[A-Za-z0-9]{1,16}',pin):
        raise APIProblem('Invalid confirmation_code.')
    if country not in ('kr','en','jp','tw') or type(game_version) is not int or game_version<1:
        raise APIProblem('Invalid country_code or game_version.')
    cc,gv=core.CountryCode.from_code(country),core.GameVersion(game_version)
    client=core.ClientInfo(cc,gv).get_client_info()
    client['pin']=pin
    encoded=core.JsonFile.from_object(client).to_data(indent=None).to_str().replace(' ','')
    url=core.ServerHandler.save_url+'/v2/transfers/'+transfer_code+'/reception'
    factory=current_app.config.get('EDITOR_RECEIVE_FACTORY')
    response=factory(url,encoded) if factory else core.RequestHandler(url,{
        'content-type':'application/json','accept-encoding':'gzip','connection':'keep-alive',
        'user-agent':'Dalvik/2.1.0 (Linux; U; Android 9; SM-G955F Build/N2G48B)'},core.Data(encoded)).post()
    if response is None:
        raise APIProblem('Transfer reception was not confirmed. Do not automatically retry.',502,retry_safe=False)
    if not response.headers.get('content-type','').startswith('application/octet-stream'):
        raise APIProblem('Transfer code/PIN was not accepted.',422,retry_safe=False)
    raw=response.content
    g.editor_original = raw
    if len(raw)>MAX_SAVE:
        raise APIProblem('Received save exceeds the supported size.',413,retry_safe=False)
    try:
        _,sf=input_save({'save_base64':b64(raw),'country_code':country})
    except APIProblem:
        raise APIProblem('Received file could not be parsed; preserve the backup.',422,
                         backup_base64=b64(raw),retry_safe=False) from None
    sh=handler(sf)
    refresh=response.headers.get('Nyanko-Password-Refresh-Token')
    password=response.headers.get('Nyanko-Password')
    if refresh is not None:
        sf.password_refresh_token=refresh
    if password is not None:
        sh.save_password(password)
    return raw,sf,sh

@bp.post('/save/from-transfer')
@remote_recovery
def from_transfer():
    data=body()
    with scoped_runtime():
        raw,sf,sh=receive_transfer(data.get('transfer_code'),data.get('confirmation_code'),
                                   data.get('country_code','kr'),data.get('game_version',150500))
        recovery=sf.to_data().data
    return jsonify(success=True,save_base64=b64(recovery),backup_base64=b64(raw),
                   **file_metadata(recovery,sf),transfer_received=True,retry_safe=False,
                   message='Transfer reception consumes the supplied code. Preserve save_base64 with the refreshed credentials.')

@bp.post('/save/upload')
@remote_recovery
def upload():
    with scoped_runtime():
        original,sf=input_save(body())
        serialize_checked(sf)
        sh=handler(sf)
        codes=sh.get_codes(tries=1)
        recovery=sf.to_data().data
        if not confirmed_codes(codes):
            raise APIProblem('Upload/code issuance was not confirmed.',502,backup_base64=b64(original),
                             save_base64=b64(recovery),retry_safe=False)
        return jsonify(success=True,transfer_code=codes[0],confirmation_code=codes[1],
                       save_base64=b64(recovery),backup_base64=b64(original),retry_safe=False)

@bp.post('/account/new')
@remote_recovery
def new_account():
    with scoped_runtime():
        original,sf=input_save(body())
        serialize_checked(sf)
        old=sf.inquiry_code
        sh=handler(sf)
        ok=sh.create_new_account(tries=1)
        valid=ok is True and bool(sf.inquiry_code) and sf.inquiry_code!=old
        if not valid:
            raise APIProblem('New account creation/synchronization was not confirmed.',502,
                             backup_base64=b64(original),save_base64=b64(sf.to_data().data),retry_safe=False)
        raw=sf.to_data().data
        return jsonify(success=True,save_base64=b64(raw),backup_base64=b64(original),**file_metadata(raw,sf),
                       retry_safe=False,message='New account credentials created. Upload separately to obtain transfer codes.')

@bp.post('/account/upload-items')
@remote_recovery
def upload_items():
    with scoped_runtime():
        original,sf=input_save(body())
        sh=handler(sf)
        ok=sh.upload_meta_data()
        if ok is not True:
            raise APIProblem('Item metadata upload was not confirmed.',502,backup_base64=b64(original),retry_safe=False)
        return jsonify(success=True,save_base64=b64(sf.to_data().data),backup_base64=b64(original),retry_safe=False)

@bp.post('/account/convert-region')
@remote_recovery
def convert_region():
    data=body()
    country=data.get('target_country_code')
    if country not in ('kr','en','jp','tw'):
        raise APIProblem('Invalid target_country_code.')
    with scoped_runtime():
        original,sf=input_save(data)
        old=sf.inquiry_code
        sf.set_cc(core.CountryCode.from_code(country))
        sh=handler(sf)
        ok=sh.create_new_account(tries=1)
        if ok is not True or not sf.inquiry_code or sf.inquiry_code==old:
            raise APIProblem('Region conversion/new account was not confirmed.',502,
                             backup_base64=b64(original),save_base64=b64(sf.to_data().data),retry_safe=False)
        raw,parsed=serialize_checked(sf)
    return jsonify(success=True,save_base64=b64(raw),backup_base64=b64(original),**file_metadata(raw,parsed),retry_safe=False)

@bp.get('/metadata/versions')
def versions():
    from editor_metadata import metadata_versions
    with scoped_runtime():
        return jsonify(success=True,versions=metadata_versions())

@bp.post('/metadata/prepare')
def prepare():
    from editor_metadata import prepare_metadata
    data=body()
    if data.get('country_code') not in ('kr','en','jp','tw') or type(data.get('game_version')) is not int or data['game_version']<1:
        raise APIProblem('Provide country_code and a positive integer game_version.')
    with scoped_runtime():
        return jsonify(success=True,**prepare_metadata(data['country_code'],data['game_version']))

@bp.delete('/metadata/cache')
def clear_metadata():
    from editor_metadata import delete_metadata
    data=body()
    if set(data)-{'country_code','game_version'}:
        raise APIProblem('Unknown metadata cache fields.')
    with scoped_runtime():
        return jsonify(success=True,**delete_metadata(data.get('country_code'),data.get('game_version')))

@bp.get('/editor/config')
def configuration():
    with scoped_runtime():
        return jsonify(success=True,defaults={k.value:v for k,v in core.Config.get_defaults().items()},
                       maxima=core.core_data.max_value_manager.as_dict(),
                       scope='Editing flags and limits are supplied per action. Terminal-only preferences do not affect this API.')

def register_editor_api(app,spec):
    app.register_blueprint(bp)
    spec.setdefault('components',{}).setdefault('securitySchemes',{})['EditorToken']={
        'type':'http','scheme':'bearer','description':'EDITOR_API_KEY, or the existing TEMPLATE_API_KEY'}
    spec['components'].setdefault('schemas',{})['EditorOperation']={
        'oneOf':[{'type':'object','properties':{'action':{'const':name},'args':copy.deepcopy(value['schema'])},
                  'required':['action']+([] if StrictValidator(value['schema']).is_valid({}) else ['args']),'additionalProperties':False} for name,value in sorted(ACTIONS.items())],
        'description':'Each action has its own strict argument schema. Missing args are treated as an empty object.'}
    base_fields={'save_base64':{'type':'string','format':'byte'},
                 'country_code':{'type':'string','enum':['kr','en','jp','tw'],'default':'kr'}}
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith('/v2/'):
            continue
        path=rule.rule
        for method in sorted(rule.methods-{'HEAD','OPTIONS'}):
            op={'tags':['BCSFE Editor'],'summary':rule.endpoint.split('.')[-1].replace('_',' '),
                'responses':{'200':{'description':'Success; account endpoints still require actual game acceptance'},
                             '400':{'description':'Invalid request'},'401':{'description':'Unauthorized'},
                             '422':{'description':'Invalid edit or data-loss check failed'},
                             '502':{'description':'Upstream outcome not confirmed; do not auto-retry'}}}
            if path not in ('/v2/features','/v2/capabilities'):
                op['security']=[{'EditorToken':[]}]
            if method in ('POST','DELETE'):
                fields=copy.deepcopy(base_fields)
                required=['save_base64']
                if path=='/v2/save/edit':
                    fields.update({'operations':{'type':'array','minItems':1,'maxItems':100,
                         'items':{'$ref':'#/components/schemas/EditorOperation'}},
                         'output':{'enum':['json','file'],'default':'json'}})
                    required.append('operations')
                    op['description']='Action-specific argument schemas are available at /v2/features. All file edits are applied to a copy and reparsed before success.'
                elif path=='/v2/save/import':
                    fields={'state':{'type':'object'}};required=['state']
                elif path=='/v2/save/from-transfer':
                    fields={'transfer_code':{'type':'string'},'confirmation_code':{'type':'string'},
                            'country_code':base_fields['country_code'],'game_version':{'type':'integer','default':150500}}
                    required=['transfer_code','confirmation_code']
                elif path in ('/v2/metadata/prepare','/v2/metadata/cache'):
                    fields={'country_code':base_fields['country_code'],'game_version':{'type':'integer'}}
                    required=['country_code'] if method=='DELETE' else ['country_code','game_version']
                elif path=='/v2/account/convert-region':
                    fields['target_country_code']={'enum':['kr','en','jp','tw']};required.append('target_country_code')
                op['requestBody']={'required':True,'content':{'application/json':{'schema':{
                    'type':'object','properties':fields,'required':required,'additionalProperties':False}}}}
            spec['paths'].setdefault(path,{})[method.lower()]=op
