from __future__ import annotations
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import hmac
import io
import re
import secrets
from functools import wraps
from bcsfe_runtime import scoped_runtime

from flask import Blueprint, current_app, g, jsonify, request, send_file
from werkzeug.exceptions import HTTPException
from template_store import JSONBinStore, RecordNotFound, StoreError, setting

bp = Blueprint('templates', __name__, url_prefix='/v1')
MAX_SAVE = 1024 * 1024

class APIError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status

def now():
    return datetime.now(timezone.utc).isoformat()

def store():
    factory = current_app.config.get('TEMPLATE_STORE_FACTORY', JSONBinStore)
    return factory()

def parse_save(raw, country):
    from bcsfe import core
    if country not in ('auto', 'kr', 'en', 'jp', 'tw'):
        raise APIError('country_code must be auto, kr, en, jp or tw.')
    if not 32 <= len(raw) <= MAX_SAVE:
        raise APIError('Save must be 32 bytes to 1 MiB.')
    try:


        cc = None if country == 'auto' else core.CountryCode.from_code(country)
        sf = core.SaveFile(core.Data(raw), cc=cc)
        if not sf.verify_hash() or (country != 'auto' and sf.cc.get_code() != country):
            raise ValueError('Checksum or region mismatch')
        return sf
    except Exception:
        raise APIError('Save is invalid, unsupported, or belongs to another region.', 422) from None

def unpack(record):
    try:
        raw = base64.b64decode(record['save_base64'], validate=True)
        if len(raw) > MAX_SAVE or hashlib.sha256(raw).hexdigest() != record['sha256']:
            raise ValueError('Digest mismatch')
        return raw
    except (KeyError, ValueError, TypeError, binascii.Error):
        raise StoreError('Stored save integrity check failed.') from None

def describe(record, template_id=None):
    fields = ('name', 'country_code', 'game_version', 'bytes', 'sha256', 'created_at', 'clone_ready')
    result = {key: record[key] for key in fields if key in record}
    if template_id:
        result['template_id'] = template_id
    return result

def uploaded_save():
    if request.mimetype == 'multipart/form-data':
        file = request.files.get('file')
        if file is None:
            raise APIError('Attach the raw save file in field file.')
        raw = file.read(MAX_SAVE + 1)
        data = request.form
    else:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get('save_base64'), str):
            raise APIError('Provide save_base64 or a multipart file.')
        if len(data['save_base64']) > (MAX_SAVE + 2) // 3 * 4:
            raise APIError('Save is too large.', 413)
        try:
            raw = base64.b64decode(data['save_base64'], validate=True)
        except (ValueError, binascii.Error):
            raise APIError('save_base64 is invalid.') from None
    country = data.get('country_code', 'kr')
    name = data.get('name', 'Backup')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise APIError('name must contain 1 to 100 characters.')
    sf = parse_save(raw, country)
    record = {
        'name': name.strip(), 'country_code': sf.cc.get_code(),
        'game_version': sf.game_version.game_version, 'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(), 'created_at': now(),
        'save_base64': base64.b64encode(raw).decode('ascii'),
    }
    try:
        record['clone_ready'] = sf.to_data().data == raw
    except Exception:
        record['clone_ready'] = False
    return record

def attachment(raw, name):
    return send_file(io.BytesIO(raw), mimetype='application/octet-stream',
                     as_attachment=True, download_name=name, max_age=0)

def isolated(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        with scoped_runtime():
            return function(*args,**kwargs)
    return wrapped


@bp.before_request
def authorize():
    if request.method == 'OPTIONS' or request.endpoint in ('templates.file_backup', 'templates.save_template'):
        return None
    key = setting('TEMPLATE_API_KEY')
    supplied = request.headers.get('Authorization', '')
    admin = len(key) >= 32 and hmac.compare_digest(supplied.encode(), ('Bearer ' + key).encode())
    if request.endpoint in ('templates.list_templates', 'templates.list_records'):
        if not admin:
            raise APIError('Administrator access is required for global listings.', 403)
        return None
    token = request.headers.get('X-Backup-Token', '')
    if not admin and re.fullmatch(r'[A-Za-z0-9_-]{43}', token) is None:
        raise APIError('Record not found.', 404)
    routes = {
        'templates.template_info': ('template', 'template_id'),
        'templates.download_template': ('template', 'template_id'),
        'templates.clone_template': ('template', 'template_id'),
        'templates.attempt': ('attempt', 'attempt_id'),
        'templates.recovery_info': ('recovery', 'recovery_id'),
        'templates.issuance': ('issuance', 'issuance_id'),
        'templates.recovery': ('recovery', 'recovery_id'),
    }
    target = routes.get(request.endpoint)
    if target is None:
        raise APIError('Record not found.', 404)
    kind, field = target
    vault = store()
    try:
        record = vault.load(request.view_args[field], kind)
        template = record if kind == 'template' else vault.load(record.get('template_id'), 'template')
    except RecordNotFound:
        raise APIError('Record not found.', 404) from None
    digest = template.get('backup_token_sha256', '')
    if not admin and (not isinstance(digest, str) or not hmac.compare_digest(
            digest.encode(), hashlib.sha256(token.encode()).hexdigest().encode())):
        raise APIError('Record not found.', 404)
    g.backup_record = record
    g.backup_store = vault

@bp.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return response

@bp.errorhandler(APIError)
def bad_request(exc):
    return jsonify(success=False, message=exc.message), exc.status

@bp.errorhandler(RecordNotFound)
def missing_record(exc):
    return jsonify(success=False, message='Record not found.'), 404

@bp.errorhandler(StoreError)
def storage_error(exc):
    return jsonify(success=False, message=str(exc)), 503

@bp.errorhandler(Exception)
def unexpected(exc):
    if isinstance(exc, HTTPException):
        return jsonify(success=False, message=exc.description), exc.code
    return jsonify(success=False, message='Template operation failed.'), 500

@bp.post('/backups')
@isolated
def file_backup():
    record = uploaded_save()
    return attachment(unpack(record), 'backup-' + record['sha256'][:12] + '.save')

@bp.post('/templates')
@isolated
def save_template():
    record = uploaded_save()
    token = secrets.token_urlsafe(32)
    record['backup_token_sha256'] = hashlib.sha256(token.encode()).hexdigest()
    template_id = store().save('template', record)
    return jsonify(success=True, backup_token=token, **describe(record, template_id)), 201

@bp.get('/templates')
def list_templates():
    return jsonify(success=True, **store().list_templates(request.args.get('cursor', '')))

@bp.get('/templates/<template_id>')
def template_info(template_id):
    return jsonify(success=True, **describe(g.backup_record, template_id))

@bp.get('/templates/<template_id>/download')
def download_template(template_id):
    record = g.backup_record
    return attachment(unpack(record), 'template-' + template_id + '.save')

def new_handler(sf):
    from bcsfe import core
    factory = current_app.config.get('TEMPLATE_HANDLER_FACTORY')
    from account_transport import HeadlessServerHandler
    return factory(sf) if factory else HeadlessServerHandler(sf, print=False)

@bp.post('/templates/<template_id>/clones')
@isolated
def clone_template(template_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('order_id'), str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', data['order_id']):
        raise APIError('Provide an order_id (1-100 letters, numbers, _, ., : or -).')
    vault = g.backup_store
    record = g.backup_record
    raw = unpack(record)
    sf = parse_save(raw, record['country_code'])
    if sf.to_data().data != raw:
        raise APIError('This save cannot be reserialized unchanged; backup download is available.', 422)
    source_identity = sf.inquiry_code
    handler = new_handler(sf)

    attempt_id = vault.save('attempt', {'template_id': template_id, 'order_id': data['order_id'],
                                       'created_at': now(), 'status': 'started'})
    recovery_id = None
    try:
        if handler.create_new_account(tries=1) is not True:
            raise APIError('New account creation was not confirmed.', 502)
        if not sf.inquiry_code or sf.inquiry_code == source_identity:
            raise APIError('A distinct account identity was not confirmed.', 502)

        recovery_raw = sf.to_data().data
        recovery_id = vault.save('recovery', {
            'template_id': template_id, 'order_id': data['order_id'], 'attempt_id': attempt_id,
            'created_at': now(), 'country_code': record['country_code'],
            'save_base64': base64.b64encode(recovery_raw).decode('ascii'),
            'sha256': hashlib.sha256(recovery_raw).hexdigest()})
        codes = handler.get_codes(tries=1)
        if not isinstance(codes, (tuple, list)) or len(codes) != 2 or not all(isinstance(v, str) and v for v in codes):
            raise APIError('Transfer code issuance was not confirmed.', 502)
        result = {
            'template_id': template_id, 'order_id': data['order_id'], 'attempt_id': attempt_id,
            'recovery_id': recovery_id, 'created_at': now(), 'status': 'issued',
            'transfer_code': codes[0], 'confirmation_code': codes[1],
        }
        try:
            result_id = vault.save('issuance', result)
        except StoreError:

            return jsonify(success=True, persisted=False, retry_safe=False, **result,
                           message='Codes issued, but result persistence failed. Save this response.'), 201
        return jsonify(success=True, persisted=True, retry_safe=False, issuance_id=result_id, **result), 201
    except Exception as exc:
        message = exc.message if isinstance(exc, APIError) else 'Issuance stopped; inspect the attempt before placing another order.'
        recovery_raw = raw
        recovery_serialized = False
        try:
            recovery_raw = sf.to_data().data
            recovery_serialized = True
        except Exception:
            pass
        return jsonify(success=False, retry_safe=False, status='needs_attention',
                       message=message, attempt_id=attempt_id, recovery_id=recovery_id,
                       backup_base64=base64.b64encode(raw).decode('ascii'),
                       save_base64=base64.b64encode(recovery_raw).decode('ascii'),
                       recovery_serialized=recovery_serialized), 502

@bp.get('/template-records')
def list_records():
    kind = request.args.get('kind', 'issuance')
    if kind not in ('attempt', 'issuance', 'recovery'):
        raise APIError('kind must be attempt, issuance or recovery.')
    return jsonify(success=True, **store().list_records(kind, request.args.get('cursor', '')))

@bp.get('/attempts/<attempt_id>')
def attempt(attempt_id):
    return jsonify(success=True, attempt_id=attempt_id, **g.backup_record)

@bp.get('/recoveries/<recovery_id>')
def recovery_info(recovery_id):
    record = g.backup_record
    return jsonify(success=True, recovery_id=recovery_id,
                   **{k: v for k, v in record.items() if k != 'save_base64'})

@bp.get('/issuances/<issuance_id>')
def issuance(issuance_id):
    return jsonify(success=True, issuance_id=issuance_id, **g.backup_record)

@bp.get('/recoveries/<recovery_id>/download')
def recovery(recovery_id):
    return attachment(unpack(g.backup_record), 'recovery-' + recovery_id + '.save')

def register_template_api(app, spec):
    app.register_blueprint(bp)
    components = spec.setdefault('components', {})
    components.setdefault('securitySchemes', {})['TemplateToken'] = {
        'type': 'http', 'scheme': 'bearer', 'description': 'Optional administrator TEMPLATE_API_KEY (at least 32 characters). Required only for global listings or access to templates created without a backup token.'}
    components['securitySchemes']['BackupToken'] = {
        'type': 'apiKey', 'in': 'header', 'name': 'X-Backup-Token',
        'description': 'The private backup_token returned once when a template is created. Grants access only to that template and its attempt, recovery and issuance records. Never put it in a URL.'}

    def object_schema(properties):
        return {'type': 'object', 'properties': properties, 'required': list(properties)}

    def reference(name):
        return {'$ref': '#/components/schemas/' + name}

    def json_response(description, schema):
        return {'description': description, 'content': {'application/json': {'schema': schema}}}

    record_id = {'type': 'string', 'minLength': 24, 'maxLength': 24, 'pattern': '^[0-9a-f]{24}$'}
    nullable_id = {'oneOf': [record_id, {'type': 'null'}]}
    cursor = {'oneOf': [record_id, {'const': ''}], 'description': 'Omit or use an empty string for the first page; otherwise use next_cursor.'}
    timestamp = {'type': 'string', 'format': 'date-time'}
    listed_timestamp = {'type': ['string', 'null'], 'description': 'Creation time reported by JSONBin, or null when unavailable.'}
    digest = {'type': 'string', 'minLength': 64, 'maxLength': 64, 'pattern': '^[0-9a-f]{64}$'}
    region = {'type': 'string', 'enum': ['kr', 'en', 'jp', 'tw']}
    order_id = {'type': 'string', 'minLength': 1, 'maxLength': 100,
                'pattern': r'^[A-Za-z0-9_.:-]{1,100}(?![\s\S])',
                'description': 'Letters, numbers, underscore, dot, colon or hyphen. An audit label, not an idempotency key.'}
    country_schema = {'type': 'string', 'enum': ['auto', 'kr', 'en', 'jp', 'tw'], 'default': 'kr',
                      'description': 'Use auto to detect the save region from its checksum. An explicit region must match the file. Defaults to kr for existing clients; stored metadata always contains the detected kr, en, jp or tw region.'}
    upload_name = {'type': 'string', 'default': 'Backup',
                   'description': 'Leading and trailing whitespace is removed. The resulting name must contain 1 to 100 characters.'}
    encoded_save = {'type': 'string', 'format': 'byte',
                    'description': 'Standard Base64 of a raw save containing 32 bytes to 1 MiB, including its original checksum.'}
    upload_schema = {'type': 'object', 'required': ['save_base64'], 'properties': {
        'save_base64': encoded_save, 'name': upload_name, 'country_code': country_schema}}
    multipart_schema = {'type': 'object', 'required': ['file'], 'properties': {
        'file': {'type': 'string', 'format': 'binary', 'description': 'Raw save file, 32 bytes to 1 MiB.'},
        'name': upload_name, 'country_code': country_schema}}
    metadata = {'success': {'const': True}, 'template_id': record_id,
                'name': {'type': 'string'}, 'country_code': region,
                'game_version': {'type': 'integer'}, 'bytes': {'type': 'integer', 'minimum': 32, 'maximum': MAX_SAVE},
                'sha256': digest, 'created_at': timestamp,
                'clone_ready': {'type': 'boolean', 'description': 'The current library can reserialize this file without changing any bytes. This does not confirm game-server acceptance.'}}
    order_fields = {'template_id': record_id, 'order_id': order_id, 'attempt_id': record_id,
                    'created_at': timestamp}
    issuance_fields = {**order_fields, 'recovery_id': record_id, 'status': {'const': 'issued'},
                       'transfer_code': {'type': 'string', 'minLength': 1},
                       'confirmation_code': {'type': 'string', 'minLength': 1}}
    clone_fields = {'success': {'const': True}, 'retry_safe': {'const': False}, **issuance_fields}
    persisted_clone = object_schema({**clone_fields, 'persisted': {'const': True}, 'issuance_id': record_id})
    unpersisted_clone = object_schema({**clone_fields, 'persisted': {'const': False}, 'message': {'type': 'string'}})
    persisted_clone['additionalProperties'] = False
    unpersisted_clone['additionalProperties'] = False
    schemas = {
        'TemplateError': object_schema({'success': {'const': False}, 'message': {'type': 'string'}}),
        'TemplateMetadata': object_schema(metadata),
        'TemplateCreated': object_schema({**metadata, 'backup_token': {
            'type': 'string', 'minLength': 43, 'maxLength': 43, 'pattern': '^[A-Za-z0-9_-]{43}$',
            'description': 'Private access token returned only in this creation response. Save it with template_id and send it as X-Backup-Token for subsequent access. It cannot be retrieved later.'}}),
        'TemplateList': object_schema({'success': {'const': True},
            'templates': {'type': 'array', 'items': object_schema({'template_id': record_id, 'created_at': listed_timestamp})},
            'next_cursor': nullable_id}),
        'TemplateRecordList': object_schema({'success': {'const': True},
            'records': {'type': 'array', 'items': object_schema({'id': record_id, 'created_at': listed_timestamp})},
            'next_cursor': nullable_id}),
        'TemplateAttempt': object_schema({'success': {'const': True}, **order_fields,
            'status': {'const': 'started', 'description': 'An immutable start marker, not a final outcome. Check issuance and recovery records.'}}),
        'TemplateRecovery': object_schema({'success': {'const': True}, 'recovery_id': record_id,
            **order_fields, 'country_code': region, 'sha256': digest}),
        'TemplateIssuance': object_schema({'success': {'const': True}, 'issuance_id': record_id, **issuance_fields}),
        'TemplateClonePersisted': persisted_clone,
        'TemplateCloneUnpersisted': unpersisted_clone,
        'TemplateCloneNeedsAttention': object_schema({'success': {'const': False}, 'retry_safe': {'const': False},
            'status': {'const': 'needs_attention'}, 'message': {'type': 'string'},
            'attempt_id': record_id, 'recovery_id': nullable_id,
            'backup_base64': {**encoded_save, 'description': 'Original template bytes, always preserved.'},
            'save_base64': {**encoded_save, 'description': 'Available current save state; it may still be the original. Falls back to the original if serialization fails.'},
            'recovery_serialized': {'type': 'boolean', 'description': 'Whether the current in-memory state could be serialized. This does not confirm that account creation succeeded.'}}),
    }
    schemas['TemplateList']['description'] = 'IDs and creation times only; request each template for full metadata. A filtered page may be empty while next_cursor is non-null.'
    schemas['TemplateRecordList']['description'] = 'IDs and creation times for the requested kind. Follow next_cursor even when records is empty.'
    schemas['TemplateRecovery']['description'] = 'Recovery metadata only. Download raw save bytes from the corresponding /download route.'
    schemas['TemplateIssuance']['description'] = 'Stored issuance result. It does not contain the immediate clone response fields persisted or retry_safe.'
    components.setdefault('schemas', {}).update(schemas)

    binary_response = {'description': 'Exact save bytes as an attachment; this response is not JSON.',
        'headers': {'Content-Disposition': {'description': 'Attachment filename.', 'schema': {'type': 'string'}}},
        'content': {'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}}}}
    operations = [
        ('/v1/backups', 'post', 'Download an exact file backup', upload_schema, binary_response),
        ('/v1/templates', 'post', 'Store an immutable private JSONBin template', upload_schema,
         json_response('Template stored. Keep template_id and the one-time backup_token.', reference('TemplateCreated'))),
        ('/v1/templates', 'get', 'List template IDs (follow next_cursor)', None,
         json_response('Template ID page.', reference('TemplateList'))),
        ('/v1/templates/{template_id}', 'get', 'Read template metadata', None,
         json_response('Template metadata without save_base64.', reference('TemplateMetadata'))),
        ('/v1/templates/{template_id}/download', 'get', 'Download the original save bytes', None, binary_response),
        ('/v1/templates/{template_id}/clones', 'post', 'Issue a separate account from a template; do not auto-retry',
         object_schema({'order_id': order_id}),
         json_response('Codes issued. Check persisted: false means result storage failed and issuance_id is absent; preserve this response.',
                       {'oneOf': [reference('TemplateClonePersisted'), reference('TemplateCloneUnpersisted')]})),
        ('/v1/template-records', 'get', 'List attempt, issuance or recovery record IDs', None,
         json_response('Record ID page for the requested kind.', reference('TemplateRecordList'))),
        ('/v1/attempts/{attempt_id}', 'get', 'Read an issuance attempt marker', None,
         json_response('Immutable attempt-start metadata.', reference('TemplateAttempt'))),
        ('/v1/recoveries/{recovery_id}', 'get', 'Read recovery metadata', None,
         json_response('Recovery metadata without save_base64.', reference('TemplateRecovery'))),
        ('/v1/issuances/{issuance_id}', 'get', 'Read saved issuance codes', None,
         json_response('Saved issuance result and codes.', reference('TemplateIssuance'))),
        ('/v1/recoveries/{recovery_id}/download', 'get', 'Download a new-account recovery save', None, binary_response),
    ]
    for path, method, summary, schema, success_response in operations:
        success_status = '201' if method == 'post' and path != '/v1/backups' else '200'
        errors = {'400': 'Invalid input.',
                  '500': 'Unexpected operation failure.', '503': 'Storage, integrity check, or configuration unavailable.'}
        public = method == 'post' and path in ('/v1/backups', '/v1/templates')
        listing = method == 'get' and path in ('/v1/templates', '/v1/template-records')
        if listing:
            errors['403'] = 'Administrator access is required for global listings.'
        if method == 'post':
            errors.update({'413': 'Request body or Base64 save is too large.', '429': 'Deployment request limit reached.'})
        if path != '/v1/backups':
            errors['404'] = 'Record not found, invalid record ID/cursor, or missing/wrong backup token. These cases share the same response.'
        if schema is upload_schema or '/clones' in path:
            errors['422'] = 'Invalid checksum, region mismatch, unsupported save, or failed clone serialization check.'
        responses = {success_status: success_response,
                     **{code: json_response(description, reference('TemplateError')) for code, description in errors.items()}}
        operation = {'tags': ['Backups and Templates'], 'summary': summary,
                     'security': [] if public else ([{'TemplateToken': []}] if listing else [{'BackupToken': []}, {'TemplateToken': []}]),
                     'responses': responses}
        if listing:
            operation['description'] = 'Administrator-only global listing. A backup token does not grant listing access; keep the IDs returned by creation and clone responses.'
        elif path == '/v1/templates' and method == 'post':
            operation['description'] = 'No API key is required. Stores encrypted immutable save bytes and returns a private backup_token once. Keep that token with template_id; future reads and clone operations require X-Backup-Token.'
        elif not public:
            operation['description'] = 'Send the associated template backup_token in X-Backup-Token. Missing, wrong and cross-template tokens return the same 404 as an unknown record.'
        if '/clones' in path:
            operation['description'] += ' Creates a separate upstream account. order_id is an audit label, not an idempotency key. The vending backend must atomically reserve each order and never auto-retry an uncertain request.'
            responses['502'] = json_response('Issuance needs attention. Preserve both Base64 files and inspect the attempt; do not retry automatically.', reference('TemplateCloneNeedsAttention'))
        elif path == '/v1/backups':
            operation['description'] = 'Validates the upload and returns the original bytes. Does not store a JSONBin template or create a game account.'
        for name in re.findall(r'{(.*?)}', path):
            operation.setdefault('parameters', []).append({'in': 'path', 'name': name, 'required': True, 'schema': record_id})
        if method == 'get' and path == '/v1/templates':
            operation['parameters'] = [{'in': 'query', 'name': 'cursor', 'schema': cursor}]
        if path == '/v1/template-records':
            operation['parameters'] = [
                {'in': 'query', 'name': 'cursor', 'schema': cursor},
                {'in': 'query', 'name': 'kind', 'schema': {'type': 'string', 'enum': ['attempt', 'issuance', 'recovery'], 'default': 'issuance'}}]
        if schema:
            operation['requestBody'] = {'required': True, 'content': {'application/json': {'schema': schema}}}
            if schema is upload_schema:
                operation['requestBody']['content']['multipart/form-data'] = {'schema': multipart_schema}
        spec['paths'].setdefault(path, {})[method] = operation
