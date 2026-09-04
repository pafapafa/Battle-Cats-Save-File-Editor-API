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

def register_service_docs(spec):
    """Describe public and legacy routes without changing their handlers."""
    from copy import deepcopy
    import editor_legacy as legacy
    from editor_engine import ACTIONS
    schemas=spec['components']['schemas']
    def obj(fields,required=()):return {'type':'object','properties':fields,'required':list(required)}
    def ref(name):return {'$ref':'#/components/schemas/'+name}
    def response(description,schema):return {'description':description,'content':{'application/json':{'schema':schema}}}
    region={'type':'string','enum':['kr','en','jp','tw']}
    token={'type':'string','minLength':1,'maxLength':64,'pattern':r'^[A-Za-z0-9]{1,64}(?![\s\S])'}
    pin={'type':'string','minLength':1,'maxLength':16,'pattern':r'^[A-Za-z0-9]{1,16}(?![\s\S])'}
    credential_props={
        'transfer_code':{**token,'description':'Transfer code to receive. Alias: tc. Reception consumes this code.'},
        'tc':{**token,'description':'Alias for transfer_code.'},
        'confirmation_code':{**pin,'description':'Transfer confirmation code/PIN. Aliases: confirmation_pin, cc.'},
        'confirmation_pin':{**pin,'description':'Alias for confirmation_code.'},
        'cc':{**pin,'description':'Legacy alias for confirmation_code; this field is not a region.'},
        'country_code':{**region,'default':'kr','description':'Source region. Aliases: country, cc_str.'},
        'country':{**region,'description':'Alias for country_code; defaults to kr when every region alias is absent.'},
        'cc_str':{**region,'description':'Alias for country_code.'}}
    credential_rules=[{'anyOf':[{'required':[name]} for name in ('transfer_code','tc')]},
                      {'anyOf':[{'required':[name]} for name in ('confirmation_code','confirmation_pin','cc')]}]
    info_request={**obj(credential_props),'allOf':credential_rules,'additionalProperties':False,
        'description':'Provide a transfer-code alias and a confirmation-code alias. Repeated aliases must have identical values. Uses game_version=150500; the legacy routes do not accept a game_version field.'}
    edit_props=deepcopy(credential_props)
    for field,action in legacy.SCALARS.items():
        key='score' if field in ('challenge_score','dojo_score') else 'value'
        edit_props[field]={**deepcopy(ACTIONS[action]['schema']['properties'][key]),'description':'Sets '+action+' ('+key+'). Zero is explicit. Optional; omission preserves the value.'}
    for field,action in legacy.VECTORS.items():
        edit_props[field]=deepcopy(ACTIONS[action]['schema']['properties']['values'])
        if field in ('catamins','catseyes'):
            edit_props[field]={'anyOf':[edit_props[field],{'type':'object','additionalProperties':{'type':'integer','minimum':0,'maximum':2147483647}}]}
        edit_props[field]['description']='Collection quantity, prefix array, or index-to-quantity object; unspecified entries are preserved. '+('Named aliases: a/b/c.' if field=='catamins' else 'Named aliases: special/ex, rare, super/super_rare, uber/uber_rare, legend, dark.' if field=='catseyes' else '')
    for field,(action,args) in legacy.SIMPLE_FLAGS.items():
        edit_props[field]={'type':'boolean','description':'When true, requests '+action+'. False performs no action. See LEGACY.md for the exact selection scope.'}
    for field,kind in legacy.MAP_FLAGS.items():
        edit_props[field]={'anyOf':[{'type':'boolean'},deepcopy(ACTIONS['stages.'+kind]['schema'])],
            'description':'True clears all valid maps/crowns in '+kind+'; false performs no action. An object uses stages.'+kind+' arguments. Use top-level enable_safety for limits.'}
    for field,(action,args) in legacy.OBJECT_OR_FLAG.items():
        edit_props[field]={'anyOf':[{'type':'boolean'},deepcopy(ACTIONS[action]['schema'])],
            'description':'True applies the documented all-selection operation; false performs no action. An object uses '+action+' arguments.'}
    details={
        'catamins_a':('integer','Set only Catamin A (stored index 0).'),
        'catamins_b':('integer','Set only Catamin B (stored index 1).'),
        'catamins_c':('integer','Set only Catamin C (stored index 2).'),
        'behemoth_stones':('object','Required shape: {item_ids: {game_item_id: quantity}}. IDs must belong to evolution items; no guessed stone offsets.'),
        'battle_items_endless':(['number','string','array','object'],'Minutes per item: nonnegative number or "infinity" for all, a prefix array, or an index mapping. Uses items.endless.'),
        'gamatoto_helpers':(['array','object'],'Helper ID array, rarity-count mapping, or explicit gamatoto.helpers argument object.'),
        'gamatoto_helper_ids':('array','Helper IDs for gamatoto.helpers.ids.'),
        'gamatoto_helper_rarities':('object','Rarity-to-count mapping for gamatoto.helpers.rarities.'),
        'ototo_materials':(['integer','array','object'],'Quantities for ototo.materials.values. Supports its scalar, array, and index-object forms.'),
        'unlock_cat_ids':('array','IDs of cats to unlock; an empty array performs no action.'),
        'remove_cat_ids':('array','IDs of cats whose unlocked status should be removed; an empty array performs no action.'),
        'cat_levels':(['array','object'],'Cat-ID mapping, record array, single id/cat_id record, or cats.levels object with select. Record base aliases: level/upgrade/base; plus aliases: plus_level/plus. Omitted component is preserved.'),
        'cat_evolutions':(['array','object'],'Cat-ID to form mapping, records with id/cat_id and form/evolution (1..4), or cats.forms object with select.'),
        'cat_talents':(['array','object'],'Cat-ID to talent-ID/level mapping, records with id/cat_id and levels/talents, or cats.talents object with select.'),
        'talent_orbs':('object','Orb-ID quantity mapping or full cats.orbs arguments. Unspecified orbs are preserved.'),
        'special_skills':(['array','object'],'Indexed level values, indexed level/plus objects, or full skills.set object with skills. Components accept integers, inclusive {min,max} ranges, or "max".'),
        'castle_development':(['integer','object'],'Development value for every valid cannon, cannon-ID mapping, or full ototo.cannons object with ids/entries.'),
        'castle_levels':('object','Cannon-ID to levels mapping or full ototo.cannons object with ids/entries.'),
        'clear_all_stages':(['boolean','object'],'True clears story, all valid stage families, Aku and tutorial. Or use {scopes: ["story", "aku", "sol", ...]}; false performs no action.'),
        'clear_chapters':('array','Chapter IDs or {chapter, clear_amount/clears} records. Chapters 0..8 are story; 9 selects all Aku maps/crowns. Clear count defaults to 1.'),
        'clear_stages':('array','{chapter, stage, clear_amount/clears} records. For chapter 9 only, map/aku_map selects Aku map and star is zero-based; defaults map=0, star=0, clears=1.'),
        'max_chapter_treasures':('array','Story chapter IDs (0..8) or {chapter, treasure} records; treasure defaults to 3.'),
        'stage_treasures':('array','{chapter, stage, treasure} records. Legacy stage uses raw treasure slot 0..47, unlike the typed action menu ordering. Treasure defaults to 3.'),
        'itf_timed_scores':(['integer','object'],'Score for all Into the Future chapters or full stages.itf_scores arguments.'),
        'event_tickets':(['boolean','object'],'False performs no action. Otherwise use {items: {game_item_id: quantity}} or that item mapping directly; true is invalid.'),
        'cat_storage':(['boolean','object'],'False performs no action. Otherwise use {operation: "add"|"remove"|"clear", ...cats.storage action arguments}; true is invalid.'),
        'cat_shrine':(['boolean','object'],'False performs no action; otherwise provide shrine.set arguments. True is invalid.'),
        'ototo_cat_cannon':(['boolean','object'],'False performs no action; otherwise provide ototo.cannons arguments. True is invalid.'),
        'playtime':(['integer','object'],'Frame count or full playtime.set argument object.'),
        'unban_account':('boolean','When true, requests a distinct new account before upload. This does not confirm reversal of an existing account ban.'),
        'upload_items':('boolean','When true, requires confirmed managed-item metadata upload before issuing transfer codes.'),
        'enable_safety':('boolean','Defaults to false. True applies recommended maxima only to actions supporting them. Save-format and metadata constraints always apply.'),
    }
    for field,(kind,description) in details.items():edit_props[field]={'type':kind,'description':description}
    edit_props['enable_safety']['default']=False
    for field in ('catamins_a','catamins_b','catamins_c'):edit_props[field].update(minimum=0,maximum=2147483647)
    for field in ('event_tickets','cat_storage','cat_shrine','ototo_cat_cannon'):
        edit_props[field]['not']={'const':True}
    for alias,canonical in legacy.ALIASES.items():
        edit_props[alias]=deepcopy(edit_props[canonical]);edit_props[alias]['description']='Alias for '+canonical+'. '+edit_props[alias].get('description','')
    assert set(edit_props)==set(legacy.SUPPORTED_FIELDS)
    edit_request={**obj(edit_props),'allOf':credential_rules,'additionalProperties':False,
        'description':'Compatibility payload. At least one effective edit or remote flag is required. Unknown fields, conflicting aliases, wrong types, and invalid action arguments fail before transfer reception where possible. Nested legacy alternatives are semantically validated by the converter; see LEGACY.md and the corresponding typed action for exact ID/range rules.'}
    schemas['LegacyInfoRequest']=info_request;schemas['LegacyEditRequest']=edit_request
    base64_value={'type':'string','format':'byte'}
    recovery={'save_base64':base64_value,'backup_base64':base64_value,'retry_safe':{'const':False}}
    metadata={key:deepcopy(schemas['EditorImportedSave']['properties'][key]) for key in ('country_code','game_version','bytes','sha256')}
    info_fields={'success':{'const':True},**{name:{'type':'integer'} for name in ('catfood','xp','normal_tickets','rare_tickets','platinum_tickets','legend_tickets','platinum_shards','np','leadership')},**metadata,**recovery,'message':{'type':'string'}}
    edit_fields={'success':{'const':True},'transfer_code':{'type':'string','minLength':1},'confirmation_code':{'type':'string','minLength':1},**recovery,
                 'changes':deepcopy(schemas['EditorEditedSave']['properties']['changes']),'change_count':{'type':'integer','minimum':0}}
    schemas['LegacyInfoResult']=obj(info_fields,info_fields)
    schemas['LegacyEditResult']=obj(edit_fields,edit_fields)
    for path,name,summary,description in (
        ('/info','Info','Receive a transfer and read legacy resource totals','Consumes the supplied transfer code, refreshes credentials, and returns resource totals plus original/current Base64 saves. It does not issue replacement codes. Prefer /v2/save/inspect for file-only reads.'),
        ('/edit','Edit','Receive, edit and re-upload using legacy fields','Converts legacy fields to typed edits, receives the transfer, applies edits, runs requested remote flags, and requests replacement transfer codes. Consumes the input code. Preserve returned recovery bytes and do not automatically repeat uncertain requests. Changes are limited to 1,000 entries; change_count is the full count.')):
        errors={'400':'Invalid/missing credentials or no effective edit.','401':'Missing or invalid editor token.','413':'Request or received file exceeds the limit.',
                '422':'Invalid legacy input/save, transfer rejection, or persistence check failed.','429':'Deployment request limit reached.',
                '500':'Unexpected service failure.','502':'Remote outcome not confirmed; preserve available recovery bytes.','503':'Editor key is not configured.'}
        spec['paths'][path]={'post':{'tags':['Legacy compatibility'],'deprecated':True,'summary':summary,'description':description,
            'security':[{'EditorToken':[]}],'requestBody':{'required':True,'content':{'application/json':{'schema':ref('Legacy'+name+'Request')}}},
            'responses':{'200':response('Confirmed result.',ref('Legacy'+name+'Result')),
                         **{code:response(text,ref('EditorError')) for code,text in errors.items()}}}}
    health_fields={'status':{'const':'online'},'service':{'type':'string'},'version':{'type':'string'},'docs':{'type':'string'},'features':{'type':'string'}}
    spec['paths']['/']={'get':{'tags':['Discovery'],'summary':'Check service availability','description':'Returns service identity and links. This does not test game-server access or JSONBin credentials.','security':[],
        'responses':{'200':response('Service identity.',obj(health_fields,health_fields))}}}
    spec['paths']['/docs']={'get':{'tags':['Discovery'],'summary':'Read the English API documentation','description':'Returns the API reference page as HTML. No authorization or account action is performed.','security':[],
        'responses':{'200':{'description':'Documentation HTML.','content':{'text/html':{'schema':{'type':'string'}}}},'500':response('Documentation could not be loaded.',ref('EditorError'))}}}
    spec['paths']['/openapi.json']={'get':{'tags':['Discovery'],'summary':'Download the OpenAPI 3.1 specification','description':'Returns all documented endpoint contracts and the shared typed edit schema. Static asset URLs and automatic HEAD/OPTIONS methods are not API entries.','security':[],
        'responses':{'200':response('OpenAPI document.',obj({'openapi':{'type':'string'},'info':{'type':'object'},'paths':{'type':'object'},'components':{'type':'object'}},['openapi','info','paths','components']))}}}

    template_descriptions={
        ('post','/v1/templates'):'Validates a raw save uploaded as JSON Base64 or multipart file, stores its unchanged bytes as an immutable private encrypted JSONBin template, and returns metadata with a template ID. country_code=auto detects the region; the default remains kr. This does not create a game account.',
        ('get','/v1/templates'):'Lists template IDs and JSONBin creation times. Request each template for its name, region, checksum and clone readiness. Continue with next_cursor until it is null, even if a filtered page is empty.',
        ('get','/v1/templates/{template_id}'):'Returns name, detected region, game version, byte length, checksum, creation time and clone readiness for one private template. Save bytes are omitted; use the download route.',
        ('get','/v1/templates/{template_id}/download'):'Loads and verifies the stored original save against its SHA-256, then returns unchanged bytes as an attachment. This does not create or modify a game account.',
        ('get','/v1/template-records'):'Lists IDs and creation times for one record kind: issuance (default), attempt, or recovery. There is no order_id filter; inspect individual records to find the order. Follow next_cursor through empty filtered pages.',
        ('get','/v1/attempts/{attempt_id}'):'Returns the immutable started marker written before a clone contacts the game server. It is not a final success/failure state; inspect issuance and recovery records for later results.',
        ('get','/v1/recoveries/{recovery_id}'):'Returns order/template/attempt references, source region, timestamp and checksum for a stored recovery save. save_base64 is omitted. Download the file separately.',
        ('get','/v1/recoveries/{recovery_id}/download'):'Returns the recovery save stored after confirmed account creation and managed-item synchronization, before transfer-code issuance. The file is verified against its stored checksum; it is not automatically restored into the game.',
        ('get','/v1/issuances/{issuance_id}'):'Returns stored transfer and confirmation codes plus order/template/attempt/recovery references and issuance time. The immediate clone response fields persisted and retry_safe are not part of this stored result.',
    }
    for (method,path),description in template_descriptions.items():
        spec['paths'][path][method]['description']=description

register_service_docs(OPENAPI_SPEC)

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
