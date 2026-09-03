"""Backup/template routes, isolated from the existing edit patcher."""
from __future__ import annotations
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import hmac
import io
import re
from functools import wraps
from bcsfe_runtime import scoped_runtime

from flask import Blueprint, current_app, jsonify, request, send_file
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
        # SaveFile detects its region from the original region-specific checksum.
        # Passing no fallback region makes an unknown checksum fail without a CLI selector.
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
    if request.method == 'OPTIONS':
        return None
    key = setting('TEMPLATE_API_KEY')
    if len(key) < 32:
        raise APIError('Template API is not configured.', 503)
    supplied = request.headers.get('Authorization', '')
    if not hmac.compare_digest(supplied.encode(), ('Bearer ' + key).encode()):
        raise APIError('A valid template Bearer token is required.', 401)

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
    return jsonify(success=False, message=str(exc)), 404

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
    template_id = store().save('template', record)
    return jsonify(success=True, **describe(record, template_id)), 201

@bp.get('/templates')
def list_templates():
    return jsonify(success=True, **store().list_templates(request.args.get('cursor', '')))

@bp.get('/templates/<template_id>')
def template_info(template_id):
    return jsonify(success=True, **describe(store().load(template_id, 'template'), template_id))

@bp.get('/templates/<template_id>/download')
def download_template(template_id):
    record = store().load(template_id, 'template')
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
    vault = store()
    record = vault.load(template_id, 'template')
    raw = unpack(record)
    sf = parse_save(raw, record['country_code'])
    if sf.to_data().data != raw:
        raise APIError('This save cannot be reserialized unchanged; backup download is available.', 422)
    source_identity = sf.inquiry_code
    handler = new_handler(sf)
    # Persist an audit marker BEFORE touching the game server. No automatic retry.
    attempt_id = vault.save('attempt', {'template_id': template_id, 'order_id': data['order_id'],
                                       'created_at': now(), 'status': 'started'})
    recovery_id = None
    try:
        if handler.create_new_account(tries=1) is not True:
            raise APIError('New account creation was not confirmed.', 502)
        if not sf.inquiry_code or sf.inquiry_code == source_identity:
            raise APIError('A distinct account identity was not confirmed.', 502)
        # Preserve the new credentials before requesting transfer codes.
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
            # The codes already exist: return them explicitly; never claim cloud persistence.
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
    return jsonify(success=True, attempt_id=attempt_id, **store().load(attempt_id, 'attempt'))

@bp.get('/recoveries/<recovery_id>')
def recovery_info(recovery_id):
    record = store().load(recovery_id, 'recovery')
    return jsonify(success=True, recovery_id=recovery_id,
                   **{k: v for k, v in record.items() if k != 'save_base64'})

@bp.get('/issuances/<issuance_id>')
def issuance(issuance_id):
    return jsonify(success=True, issuance_id=issuance_id, **store().load(issuance_id, 'issuance'))

@bp.get('/recoveries/<recovery_id>/download')
def recovery(recovery_id):
    return attachment(unpack(store().load(recovery_id, 'recovery')), 'recovery-' + recovery_id + '.save')

def register_template_api(app, spec):
    app.register_blueprint(bp)
    spec.setdefault('components', {}).setdefault('securitySchemes', {})['TemplateToken'] = {
        'type': 'http', 'scheme': 'bearer', 'description': 'Server-side TEMPLATE_API_KEY'}
    country_schema = {'type': 'string', 'enum': ['auto', 'kr', 'en', 'jp', 'tw'], 'default': 'kr',
                      'description': 'Use auto to detect the save region from its checksum. An explicit region must match the file. Defaults to kr for existing clients; stored metadata always contains the detected kr, en, jp or tw region.'}
    upload_schema = {'type': 'object', 'required': ['save_base64'], 'properties': {
        'save_base64': {'type': 'string', 'format': 'byte'},
        'name': {'type': 'string', 'maxLength': 100},
        'country_code': country_schema}}
    operations = [
        ('/v1/backups', 'post', 'Download an exact file backup', upload_schema),
        ('/v1/templates', 'post', 'Store an immutable private JSONBin template', upload_schema),
        ('/v1/templates', 'get', 'List template IDs (follow next_cursor)', None),
        ('/v1/templates/{template_id}', 'get', 'Read template metadata', None),
        ('/v1/templates/{template_id}/download', 'get', 'Download the original save bytes', None),
        ('/v1/templates/{template_id}/clones', 'post', 'Issue a separate account from a template; do not auto-retry',
         {'type': 'object', 'required': ['order_id'], 'properties': {'order_id': {'type': 'string'}}}),
        ('/v1/template-records', 'get', 'List attempt, issuance or recovery record IDs', None),
        ('/v1/attempts/{attempt_id}', 'get', 'Read an issuance attempt marker', None),
        ('/v1/recoveries/{recovery_id}', 'get', 'Read recovery metadata', None),
        ('/v1/issuances/{issuance_id}', 'get', 'Read saved issuance codes', None),
        ('/v1/recoveries/{recovery_id}/download', 'get', 'Download a new-account recovery save', None),
    ]
    for path, method, summary, schema in operations:
        operation = {'tags': ['Backups and Templates'], 'summary': summary,
            'security': [{'TemplateToken': []}],
            'responses': {('201' if method == 'post' and path != '/v1/backups' else '200'): {'description': 'Success'},
                          '400': {'description': 'Invalid input'}, '401': {'description': 'Unauthorized'},
                          '422': {'description': 'Unsupported save'}, '502': {'description': 'Issuance uncertain; no retry'},
                          '503': {'description': 'Storage or configuration unavailable'}}}
        if '/clones' in path:
            operation['description'] = 'Experimental upstream account creation. order_id is an audit label, not an idempotency key. The vending backend must atomically reserve each order and never auto-retry an uncertain request.'
        for name in re.findall(r'{(.*?)}', path):
            operation.setdefault('parameters', []).append({'in': 'path', 'name': name, 'required': True, 'schema': {'type': 'string'}})
        if method == 'get' and path == '/v1/templates':
            operation['parameters'] = [{'in': 'query', 'name': 'cursor', 'schema': {'type': 'string'}}]
        if path == '/v1/template-records':
            operation['parameters'] = [
                {'in': 'query', 'name': 'cursor', 'schema': {'type': 'string'}},
                {'in': 'query', 'name': 'kind', 'schema': {'type': 'string', 'enum': ['attempt', 'issuance', 'recovery'], 'default': 'issuance'}}]
        if schema:
            operation['requestBody'] = {'required': True, 'content': {'application/json': {'schema': schema}}}
            if schema is upload_schema:
                operation['requestBody']['content']['multipart/form-data'] = {'schema': {
                    'type': 'object', 'required': ['file'], 'properties': {
                        'file': {'type': 'string', 'format': 'binary'},
                        'name': {'type': 'string'}, 'country_code': country_schema}}}
        spec['paths'].setdefault(path, {})[method] = operation
