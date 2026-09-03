"""BCSFE HTTP service. File-first operations share one validated editor."""
from collections import defaultdict, deque
from pathlib import Path
import time
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException
from bcsfe_runtime import scoped_runtime
from editor_api import (APIProblem, auth, b64, body, confirmed_codes, file_metadata,
                        handler, receive_transfer, register_editor_api, remote_recovery)
from editor_engine import EditError, apply_operations, comparable, validate_operations
from editor_legacy import CREDENTIAL_FIELDS, legacy_to_operations
from template_api import register_template_api

app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=2*1024*1024
IP_MINUTE_HISTORY=defaultdict(deque)
IP_DAILY_HISTORY=defaultdict(deque)
MAX_PER_MINUTE=10
MAX_PER_DAY=100

@app.before_request
def rate_limit():
    if request.method!='POST' or app.testing:
        return
    now=time.time()
    ip=request.headers.get('X-Forwarded-For',request.remote_addr or 'local').split(',')[0].strip()
    for history,window,maximum in ((IP_MINUTE_HISTORY,60,MAX_PER_MINUTE),(IP_DAILY_HISTORY,86400,MAX_PER_DAY)):
        queue=history[ip]
        while queue and queue[0]<now-window:
            queue.popleft()
        if len(queue)>=maximum:
            return jsonify(success=False,message='Request limit reached; wait before retrying.'),429
    IP_MINUTE_HISTORY[ip].append(now)
    IP_DAILY_HISTORY[ip].append(now)
    if len(IP_DAILY_HISTORY)>10000:
        for key in list(IP_DAILY_HISTORY):
            if not IP_DAILY_HISTORY[key] or IP_DAILY_HISTORY[key][-1]<now-86400:
                IP_DAILY_HISTORY.pop(key,None)
                IP_MINUTE_HISTORY.pop(key,None)

@app.after_request
def response_headers(response):
    response.headers['Cache-Control']='no-store' if request.method=='POST' or response.headers.get('Cache-Control')=='no-store' else 'no-cache'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

OPENAPI_SPEC={'openapi':'3.1.0','info':{
    'title':'BCSFE API','version':'2.0.0',
    'description':'Typed API using the supplied BCSFE 3.6.0 source. File edits are atomic and checked by binary reparse. See /v2/features for exact argument schemas and source coverage.'},
    'paths':{},'components':{}}
register_template_api(app,OPENAPI_SPEC)
register_editor_api(app,OPENAPI_SPEC)

@app.get('/')
def health():
    return jsonify(status='online',service='Battle Cats Save File Editor API',version='2.0.0',docs='/docs',features='/v2/features')

@app.get('/openapi.json')
def openapi():
    return jsonify(OPENAPI_SPEC)

@app.get('/docs')
def docs():
    return (Path(__file__).parent/'docs.html').read_text(encoding='utf-8')

def credentials(data):
    def value(names,default=None):
        present=[data[name] for name in names if name in data]
        if present and any(item!=present[0] for item in present):
            raise APIProblem('Conflicting credential aliases.')
        return present[0] if present else default
    return (value(('transfer_code','tc')),value(('confirmation_code','cc','confirmation_pin')),
            value(('country_code','country','cc_str'),'kr'))

@app.post('/info')
@remote_recovery
def legacy_info():
    auth()
    data=body()
    if set(data)-CREDENTIAL_FIELDS:
        raise APIProblem('Unknown info fields.')
    with scoped_runtime():
        original,sf,_=receive_transfer(*credentials(data))
        raw=sf.to_data().data
        state=comparable(sf)
        fields=('catfood','xp','normal_tickets','rare_tickets','platinum_tickets','legend_tickets','platinum_shards','np','leadership')
        return jsonify(success=True,**{field:state[field] for field in fields},**file_metadata(raw,sf),
                       save_base64=b64(raw),backup_base64=b64(original),retry_safe=False,
                       message='The supplied transfer code was consumed. Preserve save_base64; prefer /v2/save/inspect for file-only reads.')

@app.post('/edit')
@remote_recovery
def legacy_edit():
    auth()
    data=body()
    operations=legacy_to_operations(data)
    if not operations and not data.get('unban_account') and not data.get('upload_items'):
        raise APIProblem('No edit operations were requested.')
    if operations:
        validate_operations(operations)
    with scoped_runtime():
        original,sf,_=receive_transfer(*credentials(data))
        recovery=sf.to_data().data
        try:
            if operations:
                sf,raw,delta=apply_operations(sf,operations,isolate=False)
            else:
                raw,delta=recovery,[]
            sh=handler(sf)
            if data.get('unban_account'):
                old=sf.inquiry_code
                if sh.create_new_account(tries=1) is not True or not sf.inquiry_code or sf.inquiry_code==old:
                    raise APIProblem('New account creation was not confirmed.',502)
            if data.get('upload_items') and sh.upload_meta_data() is not True:
                raise APIProblem('Item upload was not confirmed.',502)
            codes=sh.get_codes(tries=1)
            if not confirmed_codes(codes):
                raise APIProblem('Save upload/code issuance was not confirmed.',502)
            return jsonify(success=True,transfer_code=codes[0],confirmation_code=codes[1],
                           save_base64=b64(sf.to_data().data),backup_base64=b64(original),
                           changes=delta[:1000],change_count=len(delta),retry_safe=False)
        except Exception as exc:
            try:
                recovery=sf.to_data().data
            except Exception:
                pass
            status=exc.status if isinstance(exc,APIProblem) else 422 if isinstance(exc,(EditError,ValueError)) else 502
            message=exc.message if isinstance(exc,APIProblem) else str(exc) if isinstance(exc,(EditError,ValueError)) else 'Operation outcome is uncertain ('+type(exc).__name__+').'
            return jsonify(success=False,message=message,backup_base64=b64(original),
                           save_base64=b64(recovery),retry_safe=False),status

for path in ('/edit','/info'):
    OPENAPI_SPEC['paths'][path]={'post':{
        'tags':['Legacy compatibility'],'deprecated':True,
        'summary':'Legacy transfer-code operation; consumes the input transfer code',
        'security':[{'EditorToken':[]}],
        'description':'Prefer /v2/save endpoints. Strict validation replaces silent coercion. Recovery bytes are returned after reception. See LEGACY.md.',
        'requestBody':{'required':True,'content':{'application/json':{'schema':{'type':'object'}}}},
        'responses':{'200':{'description':'Confirmed result'},'422':{'description':'Invalid edit'},'502':{'description':'Unconfirmed upstream result; preserve recovery bytes'}}}}

@app.errorhandler(APIProblem)
def problem(exc):
    return jsonify(success=False,message=exc.message,**exc.details),exc.status

@app.errorhandler(EditError)
@app.errorhandler(ValueError)
def invalid(exc):
    return jsonify(success=False,message=str(exc),applied=False),422

@app.errorhandler(Exception)
def unexpected(exc):
    if isinstance(exc,HTTPException):
        return jsonify(success=False,message=exc.description),exc.code
    return jsonify(success=False,message='Operation failed ('+type(exc).__name__+').'),500

if __name__=='__main__':
    app.run(host='127.0.0.1',port=5000)
