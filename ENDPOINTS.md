# HTTP API reference

This guide covers every explicit HTTP API route. `/openapi.json` is the machine-readable OpenAPI 3.1 contract; `/v2/features` supplies the typed action argument schemas. Static assets and automatic HEAD/OPTIONS handling are not separate API operations.

All example IDs, codes, hashes, quantities, version lists and save placeholders are synthetic. Replace them with your own input. Response previews may abbreviate large state/configuration/catalog objects; this is explicitly noted below. No example claims a live account was created.

## Authentication and common behavior

- Editing, file inspection, import/export, transfers, account operations, metadata reads, `POST /v1/backups`, and `POST /v1/templates` require no client API key.
- `POST /v1/templates` returns a private `backup_token` once. Keep it with `template_id` and send `X-Backup-Token: <backup_token>` to read, download, copy, or inspect records belonging to that backup.
- `GET /v1/templates`, `GET /v1/template-records`, and `DELETE /v2/metadata/cache` are operator-only. They use `Authorization: Bearer <TEMPLATE_API_KEY>` when that optional server key is configured.
- JSON input uses `Content-Type: application/json`. Only the two v1 upload routes also accept multipart `file`.
- Raw input saves: 32 bytes through 1 MiB. The deployment request-body limit is 2 MiB. POST requests are limited per process to 10/minute and 100/day per forwarded client IP. These counters are not a distributed quota.
- Error bodies contain `success: false` and `message`. Remote failures may add recovery bytes and `retry_safe: false`; no automatic retry is safe after an uncertain account operation.
- Private/file responses use `Cache-Control: no-store`. File downloads are raw `application/octet-stream` attachments, not Base64 JSON responses.

Generic error example:
```json
{
  "success": false,
  "message": "Save cannot be parsed or its checksum/region is invalid."
}
```

## File upload examples

Private template via multipart:

```sh
curl -X POST "$API_URL/v1/templates" \
  -F "file=@account.save" -F "country_code=auto" -F "name=Starter"
```

Exact file backup without JSONBin storage:

```sh
curl -X POST "$API_URL/v1/backups" \
  -F "file=@account.save" -F "country_code=auto" --output backup.save
```

Lossless JSON export/import uses the complete exported object:

```python
exported = requests.post(base + "/v2/save/export", json=file_payload).json()
imported = requests.post(base + "/v2/save/import", json={"state": exported["state"]})
```

## Discovery and documentation

Public service information, API contracts, and source coverage.

### `GET /`

Check service availability. Returns service identity and links. This does not test game-server access or JSONBin credentials.

Authentication: none (public).

Synthetic response preview:

```json
{
  "status": "online",
  "service": "Battle Cats Save File Editor API",
  "version": "2.0.0",
  "docs": "/docs",
  "features": "/v2/features"
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Service identity. |



- No Bearer token is required. Service availability does not verify upstream services.



### `GET /docs`

Read the English API documentation. Returns the API reference page as HTML. No authorization or account action is performed.

Authentication: none (public).

Synthetic response preview:

```text
<!doctype html> ... English API documentation ...
```

| Status | Content / meaning |
| --- | --- |
| 200 | text/html — Documentation HTML. |
| 500 | application/json — Documentation could not be loaded. |



- Returns text/html. This is documentation, not a backup-management application.



### `GET /openapi.json`

Download the OpenAPI 3.1 specification. Returns all documented endpoint contracts and the shared typed edit schema. Static asset URLs and automatic HEAD/OPTIONS methods are not API entries.

Authentication: none (public).

Synthetic response preview:

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "BCSFE API",
    "version": "2.0.0"
  },
  "paths": {},
  "components": {}
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — OpenAPI document. |



- This response preview omits the actual paths and shared schemas; the live response includes them.



### `GET /v2/features`

List typed edit actions and source-feature coverage. Returns action-specific JSON Schemas, source references and recorded verification scope. Counts are not a guarantee of every possible save or live account outcome.

Authentication: none (public).

Synthetic response preview:

```json
{
  "success": true,
  "reference": "User-provided BCSFE 3.6.0 source",
  "actions": {
    "items.xp": {
      "description": "Set xp without changing other resources.",
      "schema": {
        "type": "object",
        "properties": {
          "value": {
            "type": "integer",
            "minimum": 0,
            "maximum": 2147483647
          },
          "respect_maxima": {
            "type": "boolean",
            "default": true
          }
        },
        "required": [
          "value"
        ],
        "additionalProperties": false
      },
      "source": "cli/edits/basic_items.py:BasicItems"
    }
  },
  "features": {
    "reference": {
      "name": "User-provided BCSFE source",
      "version": "3.6.0"
    },
    "counts": {
      "registered_typed_actions": 89
    },
    "items": [],
    "verification_scope": "Offline real-save integration examples; not exhaustive live-account verification.",
    "limitations": [],
    "full_cli_behavioral_equivalence": false,
    "live_game_accounts_verified": false
  }
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |



- This preview includes one action and abbreviated coverage. The live response includes all registered actions and source-feature records.



### `GET /v2/capabilities`

Read supported service capabilities. Reports file editing, import/export and account-transport availability, plus operations requiring a device companion.

Authentication: none (public).

Synthetic response preview:

```json
{
  "success": true,
  "offline_editing": true,
  "json_import_export": true,
  "raw_download": true,
  "account_transport": "implemented; actual account acceptance is not automatically guaranteed",
  "device_push": {
    "available": false,
    "reason": "ADB/root require a companion running beside the device."
  },
  "external_editor_themes": {
    "available": false,
    "reason": "Terminal display customization is not used by the HTTP API."
  }
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |





## Save files and JSON

Inspect, export, import, and download existing save files.

### `POST /v2/save/inspect`

Inspect a save without editing it. Parses the supplied raw save and returns full BCSFE state and file metadata. Does not consume transfer codes or contact a game account.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `save_base64` | yes | string; Standard Base64 of the raw save, including checksum. Input must decode to 32 bytes through 1 MiB. |
| `country_code` | no | string; default "kr"; values "kr", "en", "jp", "tw"; Region of the supplied save. Must match its checksum; v2 file routes do not accept auto. |



Example JSON request:

```json
{
  "country_code": "kr",
  "save_base64": "BASE64_OF_SAVE_FILE"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "country_code": "kr",
  "game_version": 150500,
  "bytes": 32768,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "state": {
    "cc": "kr",
    "game_version": 150500
  }
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |
| 429 | application/json — Deployment request limit reached. |



- The state preview is abbreviated. The live response contains the complete version-dependent save object. Keep all fields when importing.

- country_code defaults to kr and must match the file; auto is supported only by v1 backup/template uploads.



### `POST /v2/save/export`

Export a raw save as full BCSFE JSON state. Returns the same state representation as inspect, suitable for /v2/save/import. Preserve all fields and special-number strings.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `save_base64` | yes | string; Standard Base64 of the raw save, including checksum. Input must decode to 32 bytes through 1 MiB. |
| `country_code` | no | string; default "kr"; values "kr", "en", "jp", "tw"; Region of the supplied save. Must match its checksum; v2 file routes do not accept auto. |



Example JSON request:

```json
{
  "country_code": "kr",
  "save_base64": "BASE64_OF_SAVE_FILE"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "country_code": "kr",
  "game_version": 150500,
  "bytes": 32768,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "state": {
    "cc": "kr",
    "game_version": 150500
  }
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |
| 429 | application/json — Deployment request limit reached. |



- The state preview is abbreviated. The live response contains the complete version-dependent save object. Keep all fields when importing.

- country_code defaults to kr and must match the file; auto is supported only by v1 backup/template uploads.



### `POST /v2/save/import`

Import complete BCSFE state into a raw save. Accepts the full state from inspect/export, validates that every value survives deserialization and binary reparse, and returns Base64. Partial objects and discarded fields fail.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `state` | yes | object (`BCSFEState`); Full version-dependent object returned by inspect/export. Keep every field, nested value and numeric-key mapping when importing. Non-finite numeric values are represented as "Infinity", "-Infinity" or "NaN" strings. Additional state fields are required by the actual save model; cc and game_version alone are not an importable save. |



Example JSON request:

```json
{
  "state": {
    "cc": "kr",
    "game_version": 150500
  }
}
```

Synthetic response preview:

```json
{
  "success": true,
  "country_code": "kr",
  "game_version": 150500,
  "bytes": 32768,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "save_base64": "BASE64_OF_IMPORTED_SAVE"
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |
| 429 | application/json — Deployment request limit reached. |



- The displayed state is abbreviated for readability and is not a complete importable save. Replace it with the entire state object returned by /v2/save/export.

- Use requests.post(url, json={"state": exported_response["state"]}) to pass the complete object. Unknown or lost fields cause 422.



### `POST /v2/save/download`

Download the validated original save. Returns the exact input bytes as backup.save without editing or cloud storage.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `save_base64` | yes | string; Standard Base64 of the raw save, including checksum. Input must decode to 32 bytes through 1 MiB. |
| `country_code` | no | string; default "kr"; values "kr", "en", "jp", "tw"; Region of the supplied save. Must match its checksum; v2 file routes do not accept auto. |



Example JSON request:

```json
{
  "country_code": "kr",
  "save_base64": "BASE64_OF_SAVE_FILE"
}
```

Synthetic response preview:

```text
Binary original-save attachment: backup.save
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/octet-stream — Raw save attachment; not JSON. |
| 500 | application/json — Unexpected service failure. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |
| 429 | application/json — Deployment request limit reached. |



- The 200 response is application/octet-stream, not a JSON success object. Original bytes are returned unchanged.



## Typed save editing

Apply validated edit actions and receive persisted changes.

### `POST /v2/save/edit`

Apply a batch of typed edits atomically. Validates 1–100 operations, edits a copy, serializes and reparses it, and rejects data loss. No partial output is returned on failure. Some actions download static metadata. JSON changes are limited to 1,000 entries; change_count reports the total.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `save_base64` | yes | string; Standard Base64 of the raw save, including checksum. Input must decode to 32 bytes through 1 MiB. |
| `country_code` | no | string; default "kr"; values "kr", "en", "jp", "tw"; Region of the supplied save. Must match its checksum; v2 file routes do not accept auto. |
| `operations` | yes | array;  |
| `output` | no | string; default "json"; values "json", "file"; json returns original/edited Base64 plus changes; file returns only the edited attachment. |



Example JSON request:

```json
{
  "country_code": "kr",
  "save_base64": "BASE64_OF_SAVE_FILE",
  "operations": [
    {
      "action": "items.xp",
      "args": {
        "value": 4321
      }
    }
  ],
  "output": "json"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "applied": true,
  "country_code": "kr",
  "game_version": 150500,
  "bytes": 32768,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "save_base64": "BASE64_OF_EDITED_SAVE",
  "backup_base64": "BASE64_OF_ORIGINAL_SAVE",
  "changes": [
    {
      "path": "/xp",
      "before": 1234,
      "after": 4321
    }
  ],
  "change_count": 1,
  "changes_truncated": false
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json, application/octet-stream — Edited save. Content type depends on output: application/json or application/octet-stream. |
| 500 | application/json — Unexpected service failure. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |
| 429 | application/json — Deployment request limit reached. |



- output defaults to json. output=file returns edited.save and X-Save-SHA256, with no JSON backup field; retain your original input file.

- Use /v2/features or EditorOperation in OpenAPI for each action. IDs, metadata limits and binary persistence are checked at runtime.

- A rejected batch returns no partially edited save. Some actions download static game metadata but file editing does not contact a game account.



## Account transfers

Receive transfers, create credentials, upload saves, and synchronize item metadata.

### `POST /v2/save/from-transfer`

Receive a transfer and preserve refreshed credentials. Contacts the game server and consumes the supplied transfer code. Returns received original bytes and a current save with refreshed credentials. Do not automatically repeat an uncertain request.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `transfer_code` | yes | string;  |
| `confirmation_code` | yes | string;  |
| `country_code` | no | string; default "kr"; values "kr", "en", "jp", "tw"; Region of the supplied save. Must match its checksum; v2 file routes do not accept auto. |
| `game_version` | no | integer; default 150500; minimum 1;  |



Example JSON request:

```json
{
  "transfer_code": "SOURCE123",
  "confirmation_code": "1234",
  "country_code": "kr",
  "game_version": 150500
}
```

Synthetic response preview:

```json
{
  "success": true,
  "country_code": "kr",
  "game_version": 150500,
  "bytes": 32768,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "save_base64": "BASE64_OF_CURRENT_SAVE",
  "backup_base64": "BASE64_OF_ORIGINAL_SAVE",
  "retry_safe": false,
  "transfer_received": true,
  "message": "Transfer reception consumes the supplied code. Preserve save_base64 with the refreshed credentials."
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |
| 429 | application/json — Deployment request limit reached. |
| 502 | application/json — Remote outcome not confirmed. Preserve available recovery bytes; do not automatically retry. |



- This consumes the input transfer code. Store save_base64 containing refreshed credentials. backup_base64 contains the bytes received before those updates.

- Defaults: country_code=kr, game_version=150500. Do not automatically retry uncertain reception.



### `POST /v2/save/upload`

Upload a save and issue transfer codes. Validates save serialization, then calls the original upload/code issuance flow once. Returns available recovery bytes and confirmed codes. Do not automatically retry uncertain outcomes.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `save_base64` | yes | string; Standard Base64 of the raw save, including checksum. Input must decode to 32 bytes through 1 MiB. |
| `country_code` | no | string; default "kr"; values "kr", "en", "jp", "tw"; Region of the supplied save. Must match its checksum; v2 file routes do not accept auto. |



Example JSON request:

```json
{
  "country_code": "kr",
  "save_base64": "BASE64_OF_SAVE_FILE"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "save_base64": "BASE64_OF_CURRENT_SAVE",
  "backup_base64": "BASE64_OF_ORIGINAL_SAVE",
  "retry_safe": false,
  "transfer_code": "SAMPLE_TRANSFER",
  "confirmation_code": "1234"
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |
| 429 | application/json — Deployment request limit reached. |
| 502 | application/json — Remote outcome not confirmed. Preserve available recovery bytes; do not automatically retry. |



- Issues transfer codes through the game server. A failed or interrupted request may already have changed remote state.

- The success response does not include country_code, game_version, bytes or sha256 metadata.



### `POST /v2/account/new`

Create separate account credentials from a save. Creates a new account and synchronizes managed items; success requires a changed, nonempty inquiry code. Returns the new save. Call /v2/save/upload separately to obtain transfer codes.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `save_base64` | yes | string; Standard Base64 of the raw save, including checksum. Input must decode to 32 bytes through 1 MiB. |
| `country_code` | no | string; default "kr"; values "kr", "en", "jp", "tw"; Region of the supplied save. Must match its checksum; v2 file routes do not accept auto. |



Example JSON request:

```json
{
  "country_code": "kr",
  "save_base64": "BASE64_OF_SAVE_FILE"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "country_code": "kr",
  "game_version": 150500,
  "bytes": 32768,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "save_base64": "BASE64_OF_CURRENT_SAVE",
  "backup_base64": "BASE64_OF_ORIGINAL_SAVE",
  "retry_safe": false,
  "message": "New account credentials created. Upload separately to obtain transfer codes."
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |
| 429 | application/json — Deployment request limit reached. |
| 502 | application/json — Remote outcome not confirmed. Preserve available recovery bytes; do not automatically retry. |



- Creates credentials and synchronizes managed items. This route does not issue transfer codes; call /v2/save/upload separately.



### `POST /v2/account/upload-items`

Upload managed-item metadata. Calls the original metadata upload operation and requires an explicit true result. Does not issue transfer codes. Preserve returned save and backup bytes.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `save_base64` | yes | string; Standard Base64 of the raw save, including checksum. Input must decode to 32 bytes through 1 MiB. |
| `country_code` | no | string; default "kr"; values "kr", "en", "jp", "tw"; Region of the supplied save. Must match its checksum; v2 file routes do not accept auto. |



Example JSON request:

```json
{
  "country_code": "kr",
  "save_base64": "BASE64_OF_SAVE_FILE"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "save_base64": "BASE64_OF_CURRENT_SAVE",
  "backup_base64": "BASE64_OF_ORIGINAL_SAVE",
  "retry_safe": false
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |
| 429 | application/json — Deployment request limit reached. |
| 502 | application/json — Remote outcome not confirmed. Preserve available recovery bytes; do not automatically retry. |



- Uploads managed-item metadata, not a replacement transfer code.



### `POST /v2/account/convert-region`

Convert region and create destination account credentials. Changes the save region, requests new account credentials, and verifies persisted output. Returns a new-region save; upload separately to request transfer codes.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `save_base64` | yes | string; Standard Base64 of the raw save, including checksum. Input must decode to 32 bytes through 1 MiB. |
| `country_code` | no | string; default "kr"; values "kr", "en", "jp", "tw"; Region of the supplied save. Must match its checksum; v2 file routes do not accept auto. |
| `target_country_code` | yes | string; values "kr", "en", "jp", "tw";  |



Example JSON request:

```json
{
  "country_code": "kr",
  "save_base64": "BASE64_OF_SAVE_FILE",
  "target_country_code": "en"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "country_code": "en",
  "game_version": 150500,
  "bytes": 32768,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "save_base64": "BASE64_OF_CURRENT_SAVE",
  "backup_base64": "BASE64_OF_ORIGINAL_SAVE",
  "retry_safe": false
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |
| 429 | application/json — Deployment request limit reached. |
| 502 | application/json — Remote outcome not confirmed. Preserve available recovery bytes; do not automatically retry. |



- country_code identifies the input file; target_country_code selects the new account region. It is required and has no default.

- Returns new credentials in the save. Upload separately if you need transfer codes.



## Backups and private templates

Download exact backups and store immutable private originals.

### `POST /v1/backups`

Download an exact file backup. Validates the upload and returns the original bytes. Does not store a JSONBin template or create a game account.

Authentication: none (public).

Request body: required. Supported media types: `application/json`, `multipart/form-data`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `save_base64` | yes | string; Standard Base64 of a raw save containing 32 bytes to 1 MiB, including its original checksum. |
| `name` | no | string; default "Backup"; Leading and trailing whitespace is removed. The resulting name must contain 1 to 100 characters. |
| `country_code` | no | string; default "kr"; values "auto", "kr", "en", "jp", "tw"; Use auto to detect the save region from its checksum. An explicit region must match the file. Defaults to kr for existing clients; stored metadata always contains the detected kr, en, jp or tw region. |



Example JSON request:

```json
{
  "country_code": "auto",
  "save_base64": "BASE64_OF_SAVE_FILE"
}
```

Synthetic response preview:

```text
Binary original-save attachment: backup-000000000000.save
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/octet-stream — Exact save bytes as an attachment; this response is not JSON. |
| 400 | application/json — Invalid input. |
| 500 | application/json — Unexpected operation failure. |
| 503 | application/json — Storage, integrity check, or configuration unavailable. |
| 413 | application/json — Request body or Base64 save is too large. |
| 429 | application/json — Deployment request limit reached. |
| 422 | application/json — Invalid checksum, region mismatch, unsupported save, or failed clone serialization check. |



- No API key is required. This route does not use JSONBin storage or create a template ID.

- Accepts JSON Base64 or multipart file. The 200 response is application/octet-stream even when the request is JSON.



### `POST /v1/templates`

Store an immutable private JSONBin template. Validates a raw save uploaded as JSON Base64 or multipart file, stores its unchanged bytes as an immutable encrypted JSONBin template, and returns a template ID plus a private backup token once. country_code=auto detects the region; the default remains kr. This does not create a game account.

Authentication: none (public).

Request body: required. Supported media types: `application/json`, `multipart/form-data`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `save_base64` | yes | string; Standard Base64 of a raw save containing 32 bytes to 1 MiB, including its original checksum. |
| `name` | no | string; default "Backup"; Leading and trailing whitespace is removed. The resulting name must contain 1 to 100 characters. |
| `country_code` | no | string; default "kr"; values "auto", "kr", "en", "jp", "tw"; Use auto to detect the save region from its checksum. An explicit region must match the file. Defaults to kr for existing clients; stored metadata always contains the detected kr, en, jp or tw region. |



Example JSON request:

```json
{
  "country_code": "auto",
  "save_base64": "BASE64_OF_SAVE_FILE",
  "name": "Starter"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "template_id": "0123456789abcdef01234567",
  "name": "Starter",
  "country_code": "kr",
  "game_version": 150500,
  "bytes": 32768,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "created_at": "2026-09-04T00:00:00+00:00",
  "clone_ready": true,
  "backup_token": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
}
```

| Status | Content / meaning |
| --- | --- |
| 201 | application/json — Template stored. Keep template_id and the one-time backup_token. |
| 400 | application/json — Invalid input. |
| 500 | application/json — Unexpected operation failure. |
| 503 | application/json — Storage, integrity check, or configuration unavailable. |
| 413 | application/json — Request body or Base64 save is too large. |
| 429 | application/json — Deployment request limit reached. |
| 404 | application/json — Record not found, invalid record ID/cursor, or missing/wrong backup token. These cases share the same response. |
| 422 | application/json — Invalid checksum, region mismatch, unsupported save, or failed clone serialization check. |



- No API key is required to create a backup. The server still requires JSONBIN_API_KEY for storage.

- Save the one-time backup_token with template_id; send it later as X-Backup-Token.

- Multipart alternative: file=@account.save, country_code=auto, name=Starter. Name defaults to Backup and must be 1–100 characters after trimming.

- country_code defaults to kr; auto detects kr/en/jp/tw from the original checksum. The response stores the actual region.

- clone_ready=false permits storage and download, but copy issuance will fail its serialization check.



### `GET /v1/templates`

List template IDs (follow next_cursor). This operator-only global inventory lists template IDs and JSONBin creation times. Applications normally keep IDs returned by creation instead of listing every backup.

Authentication: operator `Authorization: Bearer <TEMPLATE_API_KEY>`.

| Parameter | Location | Required | Type / behavior |
| --- | --- | --- | --- |
| `cursor` | query | no | alternatives; Omit or use an empty string for the first page; otherwise use next_cursor. |



Example query parameters (omit cursor for the first page):

```json
{
  "cursor": "0123456789abcdef01234567"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "templates": [
    {
      "template_id": "0123456789abcdef01234567",
      "created_at": "2026-09-04T00:00:00+00:00"
    }
  ],
  "next_cursor": null
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Template ID page. |
| 400 | application/json — Invalid input. |
| 500 | application/json — Unexpected operation failure. |
| 503 | application/json — Storage, integrity check, or configuration unavailable. |
| 403 | application/json — Administrator access is required for global listings. |
| 404 | application/json — Record not found, invalid record ID/cursor, or missing/wrong backup token. These cases share the same response. |



- Omit cursor for the first page. Continue until next_cursor is null, including when a filtered page is empty.

- The list contains IDs and creation times only. It requires the operator key; a backup token cannot enumerate other backups.



### `GET /v1/templates/{template_id}`

Read template metadata. Returns name, detected region, game version, byte length, checksum, creation time and clone readiness for one private template. Save bytes are omitted; use the download route.

Authentication: `X-Backup-Token` for the associated backup. The optional operator Bearer key also grants access.

| Parameter | Location | Required | Type / behavior |
| --- | --- | --- | --- |
| `template_id` | path | yes | string;  Pattern: ^[0-9a-f]{24}$. |



Synthetic response preview:

```json
{
  "success": true,
  "template_id": "0123456789abcdef01234567",
  "name": "Starter",
  "country_code": "kr",
  "game_version": 150500,
  "bytes": 32768,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "created_at": "2026-09-04T00:00:00+00:00",
  "clone_ready": true
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Template metadata without save_base64. |
| 400 | application/json — Invalid input. |
| 500 | application/json — Unexpected operation failure. |
| 503 | application/json — Storage, integrity check, or configuration unavailable. |
| 404 | application/json — Record not found, invalid record ID/cursor, or missing/wrong backup token. These cases share the same response. |



- Returns metadata only; save_base64 is omitted. Use /download for the original file.



### `GET /v1/templates/{template_id}/download`

Download the original save bytes. Loads and verifies the stored original save against its SHA-256, then returns unchanged bytes as an attachment. This does not create or modify a game account.

Authentication: `X-Backup-Token` for the associated backup. The optional operator Bearer key also grants access.

| Parameter | Location | Required | Type / behavior |
| --- | --- | --- | --- |
| `template_id` | path | yes | string;  Pattern: ^[0-9a-f]{24}$. |



Synthetic response preview:

```text
Binary original-template attachment
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/octet-stream — Exact save bytes as an attachment; this response is not JSON. |
| 400 | application/json — Invalid input. |
| 500 | application/json — Unexpected operation failure. |
| 503 | application/json — Storage, integrity check, or configuration unavailable. |
| 404 | application/json — Record not found, invalid record ID/cursor, or missing/wrong backup token. These cases share the same response. |



- Returns application/octet-stream. Integrity is checked against the stored SHA-256; no game account is contacted.



## Template copies and recovery

Issue account copies and retrieve attempt, issuance, and recovery records.

### `POST /v1/templates/{template_id}/clones`

Issue a separate account from a template; do not auto-retry. Requests account creation using the BCSFE transport. order_id is an audit label, not an idempotency key. The vending backend must atomically reserve each order and never auto-retry an uncertain request.

Authentication: `X-Backup-Token` for the associated backup. The optional operator Bearer key also grants access.

| Parameter | Location | Required | Type / behavior |
| --- | --- | --- | --- |
| `template_id` | path | yes | string;  Pattern: ^[0-9a-f]{24}$. |



Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `order_id` | yes | string; Letters, numbers, underscore, dot, colon or hyphen. An audit label, not an idempotency key. |



Example JSON request:

```json
{
  "order_id": "order-001"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "persisted": true,
  "retry_safe": false,
  "issuance_id": "3123456789abcdef01234567",
  "template_id": "0123456789abcdef01234567",
  "order_id": "order-001",
  "attempt_id": "1123456789abcdef01234567",
  "created_at": "2026-09-04T00:00:00+00:00",
  "recovery_id": "2123456789abcdef01234567",
  "status": "issued",
  "transfer_code": "SAMPLE_TRANSFER",
  "confirmation_code": "1234"
}
```

| Status | Content / meaning |
| --- | --- |
| 201 | application/json — Codes issued. Check persisted: false means result storage failed and issuance_id is absent; preserve this response. |
| 400 | application/json — Invalid input. |
| 500 | application/json — Unexpected operation failure. |
| 503 | application/json — Storage, integrity check, or configuration unavailable. |
| 413 | application/json — Request body or Base64 save is too large. |
| 429 | application/json — Deployment request limit reached. |
| 404 | application/json — Record not found, invalid record ID/cursor, or missing/wrong backup token. These cases share the same response. |
| 422 | application/json — Invalid checksum, region mismatch, unsupported save, or failed clone serialization check. |
| 502 | application/json — Issuance needs attention. Preserve both Base64 files and inspect the attempt; do not retry automatically. |



- Creates a separate game account and requests transfer codes from an immutable template. Source template bytes remain unchanged.

- order_id is an audit label, not an idempotency key. Repeating it can create another account; reserve orders atomically in your backend.

- 201 with persisted=false still contains issued codes but has no issuance_id. Save that response; do not issue again because result storage failed.

- 502 may contain backup_base64, save_base64, recovery_serialized and nullable recovery_id. Preserve the response and inspect records before further action.



### `GET /v1/template-records`

List attempt, issuance or recovery record IDs. Lists IDs and creation times for one record kind: issuance (default), attempt, or recovery. There is no order_id filter; inspect individual records to find the order. Follow next_cursor through empty filtered pages.

Authentication: operator `Authorization: Bearer <TEMPLATE_API_KEY>`.

| Parameter | Location | Required | Type / behavior |
| --- | --- | --- | --- |
| `cursor` | query | no | alternatives; Omit or use an empty string for the first page; otherwise use next_cursor. |
| `kind` | query | no | string;  Values: attempt, issuance, recovery. Default: "issuance". |



Example query parameters (omit cursor for the first page):

```json
{
  "kind": "issuance",
  "cursor": "0123456789abcdef01234567"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "records": [
    {
      "id": "3123456789abcdef01234567",
      "created_at": "2026-09-04T00:00:00+00:00"
    }
  ],
  "next_cursor": null
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Record ID page for the requested kind. |
| 400 | application/json — Invalid input. |
| 500 | application/json — Unexpected operation failure. |
| 503 | application/json — Storage, integrity check, or configuration unavailable. |
| 403 | application/json — Administrator access is required for global listings. |
| 404 | application/json — Record not found, invalid record ID/cursor, or missing/wrong backup token. These cases share the same response. |



- kind defaults to issuance; accepted values are attempt, issuance and recovery. Omit cursor on the first request.

- The response contains generic id fields. There is no order_id query filter; load records to inspect their order references.



### `GET /v1/attempts/{attempt_id}`

Read an issuance attempt marker. Returns the immutable started marker written before a clone contacts the game server. It is not a final success/failure state; inspect issuance and recovery records for later results.

Authentication: `X-Backup-Token` for the associated backup. The optional operator Bearer key also grants access.

| Parameter | Location | Required | Type / behavior |
| --- | --- | --- | --- |
| `attempt_id` | path | yes | string;  Pattern: ^[0-9a-f]{24}$. |



Synthetic response preview:

```json
{
  "success": true,
  "template_id": "0123456789abcdef01234567",
  "order_id": "order-001",
  "attempt_id": "1123456789abcdef01234567",
  "created_at": "2026-09-04T00:00:00+00:00",
  "status": "started"
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Immutable attempt-start metadata. |
| 400 | application/json — Invalid input. |
| 500 | application/json — Unexpected operation failure. |
| 503 | application/json — Storage, integrity check, or configuration unavailable. |
| 404 | application/json — Record not found, invalid record ID/cursor, or missing/wrong backup token. These cases share the same response. |



- This immutable started marker is never updated to issued/failed. Consult issuance and recovery records for later outcomes.



### `GET /v1/recoveries/{recovery_id}`

Read recovery metadata. Returns order/template/attempt references, source region, timestamp and checksum for a stored recovery save. save_base64 is omitted. Download the file separately.

Authentication: `X-Backup-Token` for the associated backup. The optional operator Bearer key also grants access.

| Parameter | Location | Required | Type / behavior |
| --- | --- | --- | --- |
| `recovery_id` | path | yes | string;  Pattern: ^[0-9a-f]{24}$. |



Synthetic response preview:

```json
{
  "success": true,
  "recovery_id": "2123456789abcdef01234567",
  "template_id": "0123456789abcdef01234567",
  "order_id": "order-001",
  "attempt_id": "1123456789abcdef01234567",
  "created_at": "2026-09-04T00:00:00+00:00",
  "country_code": "kr",
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Recovery metadata without save_base64. |
| 400 | application/json — Invalid input. |
| 500 | application/json — Unexpected operation failure. |
| 503 | application/json — Storage, integrity check, or configuration unavailable. |
| 404 | application/json — Record not found, invalid record ID/cursor, or missing/wrong backup token. These cases share the same response. |



- Metadata excludes save_base64; obtain raw bytes from /download.



### `GET /v1/recoveries/{recovery_id}/download`

Download a new-account recovery save. Returns the recovery save stored after confirmed account creation and managed-item synchronization, before transfer-code issuance. The file is verified against its stored checksum; it is not automatically restored into the game.

Authentication: `X-Backup-Token` for the associated backup. The optional operator Bearer key also grants access.

| Parameter | Location | Required | Type / behavior |
| --- | --- | --- | --- |
| `recovery_id` | path | yes | string;  Pattern: ^[0-9a-f]{24}$. |



Synthetic response preview:

```text
Binary recovery-save attachment
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/octet-stream — Exact save bytes as an attachment; this response is not JSON. |
| 400 | application/json — Invalid input. |
| 500 | application/json — Unexpected operation failure. |
| 503 | application/json — Storage, integrity check, or configuration unavailable. |
| 404 | application/json — Record not found, invalid record ID/cursor, or missing/wrong backup token. These cases share the same response. |



- Returns the recovery file stored after confirmed account creation/synchronization and before transfer-code issuance.

- A download provides a file; it does not automatically restore it into the game.



### `GET /v1/issuances/{issuance_id}`

Read saved issuance codes. Returns stored transfer and confirmation codes plus order/template/attempt/recovery references and issuance time. The immediate clone response fields persisted and retry_safe are not part of this stored result.

Authentication: `X-Backup-Token` for the associated backup. The optional operator Bearer key also grants access.

| Parameter | Location | Required | Type / behavior |
| --- | --- | --- | --- |
| `issuance_id` | path | yes | string;  Pattern: ^[0-9a-f]{24}$. |



Synthetic response preview:

```json
{
  "success": true,
  "issuance_id": "3123456789abcdef01234567",
  "template_id": "0123456789abcdef01234567",
  "order_id": "order-001",
  "attempt_id": "1123456789abcdef01234567",
  "created_at": "2026-09-04T00:00:00+00:00",
  "recovery_id": "2123456789abcdef01234567",
  "status": "issued",
  "transfer_code": "SAMPLE_TRANSFER",
  "confirmation_code": "1234"
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Saved issuance result and codes. |
| 400 | application/json — Invalid input. |
| 500 | application/json — Unexpected operation failure. |
| 503 | application/json — Storage, integrity check, or configuration unavailable. |
| 404 | application/json — Record not found, invalid record ID/cursor, or missing/wrong backup token. These cases share the same response. |



- Returns stored codes and related record IDs. The immediate clone-response fields persisted and retry_safe are not stored here.



## Metadata and configuration

Inspect available static tables, manage verified cache entries, and read defaults.

### `GET /v2/metadata/versions`

List available game-metadata versions. Reads the configured static game-metadata index. Version strings are grouped by region; this is not a list of locally cached versions.

Authentication: none (public).

Synthetic response preview:

```json
{
  "success": true,
  "versions": {
    "kr": [
      "15.5.0"
    ],
    "en": [
      "15.5.0"
    ],
    "jp": [
      "15.5.0"
    ],
    "tw": [
      "15.5.0"
    ]
  }
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |
| 422 | application/json — Metadata index could not be validated or read. |



- These are synthetic version examples. The configured index determines actual available versions.

- No API key is required.



### `POST /v2/metadata/prepare`

Prepare verified metadata for a region and version. Downloads and caches static game tables using the upstream version-selection rule. Reports requested and resolved versions, including whether they match exactly. No game account is modified.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `country_code` | yes | string; values "kr", "en", "jp", "tw";  |
| `game_version` | yes | integer; minimum 1; maximum 999999;  |



Example JSON request:

```json
{
  "country_code": "kr",
  "game_version": 150500
}
```

Synthetic response preview:

```json
{
  "success": true,
  "country_code": "kr",
  "requested_version": "15.5.0",
  "resolved_version": "15.5.0",
  "exact_match": true,
  "downloaded": true,
  "source": "https://metadata.example.invalid/index.json",
  "archive_source": "https://metadata.example.invalid/kr/15.5.0.zip"
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |
| 429 | application/json — Deployment request limit reached. |



- Both fields are required. Metadata version range is 1..999999; there is no implicit kr/default version here.

- Downloads static tables and writes temporary cache files. resolved_version may differ from requested_version.



### `DELETE /v2/metadata/cache`

Delete API-owned metadata cache entries. Deletes verified cached versions for the selected region. Omit game_version or use null to clear all verified versions in that region. Unknown/unverified entries are preserved and counted. This does not delete saves or accounts.

Authentication: operator `Authorization: Bearer <TEMPLATE_API_KEY>`.

Request body: required. Supported media types: `application/json`.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `country_code` | yes | string; values "kr", "en", "jp", "tw";  |
| `game_version` | no | integer / null; minimum 1; maximum 999999;  |



Example JSON request:

```json
{
  "country_code": "kr",
  "game_version": 150500
}
```

Synthetic response preview:

```json
{
  "success": true,
  "country_code": "kr",
  "deleted_versions": [
    "15.5.0"
  ],
  "skipped_entries": 0
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |
| 403 | application/json — Operator authorization is missing or administration is disabled. |
| 400 | application/json — Invalid or unknown request fields. |
| 413 | application/json — Request/imported/received save exceeds the size limit. |
| 422 | application/json — Invalid save, metadata, edit, or lossless persistence check failed. |



- Uses a JSON request body. country_code is required. Omit game_version or use null for all verified cached versions of that region.

- Deletes API-owned cache entries only. It does not remove save files, templates or game accounts.



### `GET /v2/editor/config`

Read editor defaults and recommended maxima. Returns original BCSFE configuration defaults, current recommended maximum values, and the scope of action-level settings. Does not change configuration.

Authentication: none (public).

Synthetic response preview:

```json
{
  "success": true,
  "defaults": {},
  "maxima": {},
  "scope": "Editing flags and limits are supplied per action. Terminal-only preferences do not affect this API."
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Success. |
| 500 | application/json — Unexpected service failure. |



- The preview omits the many default/maxima entries. The live response includes them.

- Read-only; use action arguments such as respect_maxima to choose behavior per request.



## Transfer workflows

Receive account transfers, inspect their saves, or edit and issue replacement codes.

### `POST /info`

Receive a transfer and read resource totals. Consumes the supplied transfer code, refreshes credentials, and returns resource totals plus original/current Base64 saves. It does not issue replacement codes. Prefer /v2/save/inspect for file-only reads.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

Provide a transfer-code alias and a confirmation-code alias. Repeated aliases must have identical values. Uses game_version=150500; the transfer routes do not accept a game_version field.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `transfer_code` | no / conditional | string; Transfer code to receive. Alias: tc. Reception consumes this code. |
| `tc` | no / conditional | string; Alias for transfer_code. |
| `confirmation_code` | no / conditional | string; Transfer confirmation code/PIN. Aliases: confirmation_pin, cc. |
| `confirmation_pin` | no / conditional | string; Alias for confirmation_code. |
| `cc` | no / conditional | string; Alias for confirmation_code; this field is not a region. |
| `country_code` | no / conditional | string; default "kr"; values "kr", "en", "jp", "tw"; Source region. Aliases: country, cc_str. |
| `country` | no / conditional | string; values "kr", "en", "jp", "tw"; Alias for country_code; defaults to kr when every region alias is absent. |
| `cc_str` | no / conditional | string; values "kr", "en", "jp", "tw"; Alias for country_code. |



Example JSON request:

```json
{
  "transfer_code": "SOURCE123",
  "confirmation_code": "1234",
  "country_code": "kr"
}
```

Synthetic response preview:

```json
{
  "success": true,
  "catfood": 0,
  "xp": 0,
  "normal_tickets": 0,
  "rare_tickets": 0,
  "platinum_tickets": 0,
  "legend_tickets": 0,
  "platinum_shards": 0,
  "np": 0,
  "leadership": 0,
  "country_code": "kr",
  "game_version": 150500,
  "bytes": 32768,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "save_base64": "BASE64_OF_CURRENT_SAVE",
  "backup_base64": "BASE64_OF_ORIGINAL_SAVE",
  "retry_safe": false,
  "message": "The supplied transfer code was consumed. Preserve save_base64; prefer /v2/save/inspect for file-only reads."
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Confirmed result. |
| 400 | application/json — Invalid/missing credentials or no effective edit. |
| 413 | application/json — Request or received file exceeds the limit. |
| 422 | application/json — Invalid transfer input/save, transfer rejection, or persistence check failed. |
| 429 | application/json — Deployment request limit reached. |
| 500 | application/json — Unexpected service failure. |
| 502 | application/json — Remote outcome not confirmed; preserve available recovery bytes. |



- Transfer aliases: transfer_code/tc, confirmation_code/confirmation_pin/cc, country_code/country/cc_str. cc is the PIN, not a region.

- Conflicting aliases and extra fields fail. Uses game_version=150500; game_version is not an accepted transfer input.

- Consumes the transfer code and returns refreshed save data. Does not issue replacement codes.



### `POST /edit`

Receive, edit and re-upload using transfer-edit fields. Converts transfer-edit fields to typed edits, receives the transfer, applies edits, runs requested remote flags, and requests replacement transfer codes. Consumes the input code. Preserve returned recovery bytes and do not automatically repeat uncertain requests. Changes are limited to 1,000 entries; change_count is the full count.

Authentication: none (public).

Request body: required. Supported media types: `application/json`.

Transfer-edit payload. At least one effective edit or remote flag is required. Unknown fields, conflicting aliases, wrong types, and invalid action arguments fail before transfer reception where possible. Nested input alternatives are semantically validated by the converter; see TRANSFERS.md and the corresponding typed action for exact ID/range rules.

| JSON field | Required | Type / behavior |
| --- | --- | --- |
| `transfer_code` | no / conditional | string; Transfer code to receive. Alias: tc. Reception consumes this code. |
| `tc` | no / conditional | string; Alias for transfer_code. |
| `confirmation_code` | no / conditional | string; Transfer confirmation code/PIN. Aliases: confirmation_pin, cc. |
| `confirmation_pin` | no / conditional | string; Alias for confirmation_code. |
| `cc` | no / conditional | string; Alias for confirmation_code; this field is not a region. |
| `country_code` | no / conditional | string; default "kr"; values "kr", "en", "jp", "tw"; Source region. Aliases: country, cc_str. |
| `country` | no / conditional | string; values "kr", "en", "jp", "tw"; Alias for country_code; defaults to kr when every region alias is absent. |
| `cc_str` | no / conditional | string; values "kr", "en", "jp", "tw"; Alias for country_code. |
| `catfood` | no / conditional | integer; minimum 0; maximum 2147483647; Sets items.catfood (value). Zero is explicit. Optional; omission preserves the value. |
| `xp` | no / conditional | integer; minimum 0; maximum 2147483647; Sets items.xp (value). Zero is explicit. Optional; omission preserves the value. |
| `normal_tickets` | no / conditional | integer; minimum 0; maximum 2147483647; Sets items.normal_tickets (value). Zero is explicit. Optional; omission preserves the value. |
| `rare_tickets` | no / conditional | integer; minimum 0; maximum 2147483647; Sets items.rare_tickets (value). Zero is explicit. Optional; omission preserves the value. |
| `platinum_tickets` | no / conditional | integer; minimum 0; maximum 2147483647; Sets items.platinum_tickets (value). Zero is explicit. Optional; omission preserves the value. |
| `legend_tickets` | no / conditional | integer; minimum 0; maximum 2147483647; Sets items.legend_tickets (value). Zero is explicit. Optional; omission preserves the value. |
| `platinum_shards` | no / conditional | integer; minimum 0; maximum 2147483647; Sets items.platinum_shards (value). Zero is explicit. Optional; omission preserves the value. |
| `np` | no / conditional | integer; minimum 0; maximum 2147483647; Sets items.np (value). Zero is explicit. Optional; omission preserves the value. |
| `leadership` | no / conditional | integer; minimum 0; maximum 32767; Sets items.leadership (value). Zero is explicit. Optional; omission preserves the value. |
| `hundred_million_ticket` | no / conditional | integer; minimum 0; maximum 2147483647; Sets items.hundred_million_ticket (value). Zero is explicit. Optional; omission preserves the value. |
| `restart_pack` | no / conditional | integer; minimum 0; maximum 127; Sets items.restart_pack (value). Zero is explicit. Optional; omission preserves the value. |
| `gamatoto_level` | no / conditional | integer; minimum 1; maximum 2147483647; Sets gamatoto.level (value). Zero is explicit. Optional; omission preserves the value. |
| `gamatoto_xp` | no / conditional | integer; minimum 0; maximum 2147483647; Sets gamatoto.xp (value). Zero is explicit. Optional; omission preserves the value. |
| `ototo_engineers` | no / conditional | integer; minimum 0; maximum 2147483647; Sets ototo.engineers (value). Zero is explicit. Optional; omission preserves the value. |
| `unlocked_slots` | no / conditional | integer; minimum 0; maximum 2147483647; Sets lineups.unlocked_slots (value). Zero is explicit. Optional; omission preserves the value. |
| `challenge_score` | no / conditional | integer; minimum 0; maximum 2147483647; Sets stages.challenge_score (score). Zero is explicit. Optional; omission preserves the value. |
| `dojo_score` | no / conditional | integer; minimum 0; maximum 2147483647; Sets stages.dojo_score (score). Zero is explicit. Optional; omission preserves the value. |
| `rare_gatya_seed` | no / conditional | integer; minimum 0; maximum 4294967295; Sets gatya.rare_seed (value). Zero is explicit. Optional; omission preserves the value. |
| `normal_gatya_seed` | no / conditional | integer; minimum 0; maximum 4294967295; Sets gatya.normal_seed (value). Zero is explicit. Optional; omission preserves the value. |
| `event_gatya_seed` | no / conditional | integer; minimum 0; maximum 4294967295; Sets gatya.event_seed (value). Zero is explicit. Optional; omission preserves the value. |
| `inquiry_code` | no / conditional | string; Sets account.inquiry_code (value). Zero is explicit. Optional; omission preserves the value. |
| `password_refresh_token` | no / conditional | string; Sets account.password_refresh_token (value). Zero is explicit. Optional; omission preserves the value. |
| `catseyes` | no / conditional | alternatives; Collection quantity, prefix array, or index-to-quantity object; unspecified entries are preserved. Named aliases: special/ex, rare, super/super_rare, uber/uber_rare, legend, dark. |
| `catfruit` | no / conditional | alternatives; Collection quantity, prefix array, or index-to-quantity object; unspecified entries are preserved.  |
| `catamins` | no / conditional | alternatives; Collection quantity, prefix array, or index-to-quantity object; unspecified entries are preserved. Named aliases: a/b/c. |
| `battle_items` | no / conditional | alternatives; Collection quantity, prefix array, or index-to-quantity object; unspecified entries are preserved.  |
| `treasure_chests` | no / conditional | alternatives; Collection quantity, prefix array, or index-to-quantity object; unspecified entries are preserved.  |
| `labyrinth_medals` | no / conditional | alternatives; Collection quantity, prefix array, or index-to-quantity object; unspecified entries are preserved.  |
| `fix_gamatoto_crash` | no / conditional | boolean; When true, requests fixes.gamatoto. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `fix_ototo_crash` | no / conditional | boolean; When true, requests fixes.ototo. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `fix_time_errors` | no / conditional | boolean; When true, requests fixes.time. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `fix_officer_pass_crash` | no / conditional | boolean; When true, requests fixes.officer_pass. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `unlock_equip_menu` | no / conditional | boolean; When true, requests fixes.equip_menu. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `reset_gambling_events` | no / conditional | boolean; When true, requests gambling.reset. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `reset_golden_cat_cpus` | no / conditional | boolean; When true, requests items.golden_cpu_count. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `unlock_aku_realm` | no / conditional | boolean; When true, requests stages.unlock_aku. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `filibuster_reclearing` | no / conditional | boolean; When true, requests stages.filibuster. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `clear_tutorial` | no / conditional | boolean; When true, requests stages.tutorial. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `clear_story_all` | no / conditional | boolean; When true, requests stages.story. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `clear_into_the_future` | no / conditional | boolean; When true, requests stages.story. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `clear_cats_of_the_cosmos` | no / conditional | boolean; When true, requests stages.story. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `unlock_cats` | no / conditional | boolean; When true, requests cats.unlock. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `max_cat_levels` | no / conditional | boolean; When true, requests cats.levels. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `true_form_all` | no / conditional | boolean; When true, requests cats.forms. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `max_special_skills` | no / conditional | boolean; When true, requests skills.set. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `claim_all_rewards` | no / conditional | boolean; When true, requests rewards.claim. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `complete_missions` | no / conditional | boolean; When true, requests missions.set. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `max_all_talents` | no / conditional | boolean; When true, requests cats.talents. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `max_talent_orbs` | no / conditional | boolean; When true, requests cats.orbs. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `max_castle_development` | no / conditional | boolean; When true, requests ototo.cannons. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `max_treasures` | no / conditional | boolean; When true, requests stages.treasures. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `unlock_cat_guide` | no / conditional | boolean; When true, requests cats.guide. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `sol` | no / conditional | alternatives; True clears all valid maps/crowns in sol; false performs no action. An object uses stages.sol arguments. Use top-level enable_safety for limits. |
| `event` | no / conditional | alternatives; True clears all valid maps/crowns in event; false performs no action. An object uses stages.event arguments. Use top-level enable_safety for limits. |
| `collab` | no / conditional | alternatives; True clears all valid maps/crowns in collab; false performs no action. An object uses stages.collab arguments. Use top-level enable_safety for limits. |
| `gauntlets` | no / conditional | alternatives; True clears all valid maps/crowns in gauntlets; false performs no action. An object uses stages.gauntlets arguments. Use top-level enable_safety for limits. |
| `collab_gauntlets` | no / conditional | alternatives; True clears all valid maps/crowns in collab_gauntlets; false performs no action. An object uses stages.collab_gauntlets arguments. Use top-level enable_safety for limits. |
| `uncanny` | no / conditional | alternatives; True clears all valid maps/crowns in uncanny; false performs no action. An object uses stages.uncanny arguments. Use top-level enable_safety for limits. |
| `catamin_stages` | no / conditional | alternatives; True clears all valid maps/crowns in catamin; false performs no action. An object uses stages.catamin arguments. Use top-level enable_safety for limits. |
| `behemoth_culling` | no / conditional | alternatives; True clears all valid maps/crowns in behemoth; false performs no action. An object uses stages.behemoth arguments. Use top-level enable_safety for limits. |
| `legend_quest` | no / conditional | alternatives; True clears all valid maps/crowns in legend_quest; false performs no action. An object uses stages.legend_quest arguments. Use top-level enable_safety for limits. |
| `towers` | no / conditional | alternatives; True clears all valid maps/crowns in towers; false performs no action. An object uses stages.towers arguments. Use top-level enable_safety for limits. |
| `zero_legends` | no / conditional | alternatives; True clears all valid maps/crowns in zero_legends; false performs no action. An object uses stages.zero_legends arguments. Use top-level enable_safety for limits. |
| `dojo_catclaw_championships` | no / conditional | alternatives; True clears all valid maps/crowns in dojo_catclaw; false performs no action. An object uses stages.dojo_catclaw arguments. Use top-level enable_safety for limits. |
| `clear_enigma_stages` | no / conditional | alternatives; True clears all valid maps/crowns in enigma_clears; false performs no action. An object uses stages.enigma_clears arguments. Use top-level enable_safety for limits. |
| `outbreaks` | no / conditional | alternatives; True applies the documented all-selection operation; false performs no action. An object uses stages.outbreaks arguments. |
| `aku_chapters` | no / conditional | alternatives; True applies the documented all-selection operation; false performs no action. An object uses stages.aku arguments. |
| `medals` | no / conditional | alternatives; True applies the documented all-selection operation; false performs no action. An object uses medals.set arguments. |
| `missions` | no / conditional | alternatives; True applies the documented all-selection operation; false performs no action. An object uses missions.set arguments. |
| `enemy_guide` | no / conditional | alternatives; True applies the documented all-selection operation; false performs no action. An object uses enemy_guide.set arguments. |
| `scheme_items` | no / conditional | alternatives; True applies the documented all-selection operation; false performs no action. An object uses items.scheme arguments. |
| `catamins_a` | no / conditional | integer; minimum 0; maximum 2147483647; Set only Catamin A (stored index 0). |
| `catamins_b` | no / conditional | integer; minimum 0; maximum 2147483647; Set only Catamin B (stored index 1). |
| `catamins_c` | no / conditional | integer; minimum 0; maximum 2147483647; Set only Catamin C (stored index 2). |
| `behemoth_stones` | no / conditional | object; Required shape: {item_ids: {game_item_id: quantity}}. IDs must belong to evolution items; no guessed stone offsets. |
| `battle_items_endless` | no / conditional | number / string / array / object; Minutes per item: nonnegative number or "infinity" for all, a prefix array, or an index mapping. Uses items.endless. |
| `gamatoto_helpers` | no / conditional | array / object; Helper ID array, rarity-count mapping, or explicit gamatoto.helpers argument object. |
| `gamatoto_helper_ids` | no / conditional | array; Helper IDs for gamatoto.helpers.ids. |
| `gamatoto_helper_rarities` | no / conditional | object; Rarity-to-count mapping for gamatoto.helpers.rarities. |
| `ototo_materials` | no / conditional | integer / array / object; Quantities for ototo.materials.values. Supports its scalar, array, and index-object forms. |
| `unlock_cat_ids` | no / conditional | array; IDs of cats to unlock; an empty array performs no action. |
| `remove_cat_ids` | no / conditional | array; IDs of cats whose unlocked status should be removed; an empty array performs no action. |
| `cat_levels` | no / conditional | array / object; Cat-ID mapping, record array, single id/cat_id record, or cats.levels object with select. Record base aliases: level/upgrade/base; plus aliases: plus_level/plus. Omitted component is preserved. |
| `cat_evolutions` | no / conditional | array / object; Cat-ID to form mapping, records with id/cat_id and form/evolution (1..4), or cats.forms object with select. |
| `cat_talents` | no / conditional | array / object; Cat-ID to talent-ID/level mapping, records with id/cat_id and levels/talents, or cats.talents object with select. |
| `talent_orbs` | no / conditional | object; Orb-ID quantity mapping or full cats.orbs arguments. Unspecified orbs are preserved. |
| `special_skills` | no / conditional | array / object; Indexed level values, indexed level/plus objects, or full skills.set object with skills. Components accept integers, inclusive {min,max} ranges, or "max". |
| `castle_development` | no / conditional | integer / object; Development value for every valid cannon, cannon-ID mapping, or full ototo.cannons object with ids/entries. |
| `castle_levels` | no / conditional | object; Cannon-ID to levels mapping or full ototo.cannons object with ids/entries. |
| `clear_all_stages` | no / conditional | boolean / object; True clears story, all valid stage families, Aku and tutorial. Or use {scopes: ["story", "aku", "sol", ...]}; false performs no action. |
| `clear_chapters` | no / conditional | array; Chapter IDs or {chapter, clear_amount/clears} records. Chapters 0..8 are story; 9 selects all Aku maps/crowns. Clear count defaults to 1. |
| `clear_stages` | no / conditional | array; {chapter, stage, clear_amount/clears} records. For chapter 9 only, map/aku_map selects Aku map and star is zero-based; defaults map=0, star=0, clears=1. |
| `max_chapter_treasures` | no / conditional | array; Story chapter IDs (0..8) or {chapter, treasure} records; treasure defaults to 3. |
| `stage_treasures` | no / conditional | array; {chapter, stage, treasure} records. This stage field uses raw treasure slot 0..47, unlike the typed action menu ordering. Treasure defaults to 3. |
| `itf_timed_scores` | no / conditional | integer / object; Score for all Into the Future chapters or full stages.itf_scores arguments. |
| `event_tickets` | no / conditional | boolean / object; False performs no action. Otherwise use {items: {game_item_id: quantity}} or that item mapping directly; true is invalid. |
| `cat_storage` | no / conditional | boolean / object; False performs no action. Otherwise use {operation: "add"\|"remove"\|"clear", ...cats.storage action arguments}; true is invalid. |
| `cat_shrine` | no / conditional | boolean / object; False performs no action; otherwise provide shrine.set arguments. True is invalid. |
| `ototo_cat_cannon` | no / conditional | boolean / object; False performs no action; otherwise provide ototo.cannons arguments. True is invalid. |
| `playtime` | no / conditional | integer / object; Frame count or full playtime.set argument object. |
| `unban_account` | no / conditional | boolean; When true, requests a distinct new account before upload. This does not confirm reversal of an existing account ban. |
| `upload_items` | no / conditional | boolean; When true, requires confirmed managed-item metadata upload before issuing transfer codes. |
| `enable_safety` | no / conditional | boolean; default false; Defaults to false. True applies recommended maxima only to actions supporting them. Save-format and metadata constraints always apply. |
| `stones` | no / conditional | object; Alias for behemoth_stones. Required shape: {item_ids: {game_item_id: quantity}}. IDs must belong to evolution items; no guessed stone offsets. |
| `cat_forms` | no / conditional | array / object; Alias for cat_evolutions. Cat-ID to form mapping, records with id/cat_id and form/evolution (1..4), or cats.forms object with select. |
| `max_cat_evolutions` | no / conditional | boolean; Alias for true_form_all. When true, requests cats.forms. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `claim_rewards` | no / conditional | boolean; Alias for claim_all_rewards. When true, requests rewards.claim. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `max_talents` | no / conditional | boolean; Alias for max_all_talents. When true, requests cats.talents. False performs no action. See TRANSFERS.md for the exact selection scope. |
| `talents` | no / conditional | array / object; Alias for cat_talents. Cat-ID to talent-ID/level mapping, records with id/cat_id and levels/talents, or cats.talents object with select. |
| `orbs` | no / conditional | object; Alias for talent_orbs. Orb-ID quantity mapping or full cats.orbs arguments. Unspecified orbs are preserved. |
| `base_materials` | no / conditional | integer / array / object; Alias for ototo_materials. Quantities for ototo.materials.values. Supports its scalar, array, and index-object forms. |



Example JSON request:

```json
{
  "transfer_code": "SOURCE123",
  "confirmation_code": "1234",
  "country_code": "kr",
  "xp": 4321,
  "enable_safety": false
}
```

Synthetic response preview:

```json
{
  "success": true,
  "save_base64": "BASE64_OF_CURRENT_SAVE",
  "backup_base64": "BASE64_OF_ORIGINAL_SAVE",
  "retry_safe": false,
  "transfer_code": "SAMPLE_TRANSFER",
  "confirmation_code": "1234",
  "changes": [
    {
      "path": "/xp",
      "before": 1234,
      "after": 4321
    }
  ],
  "change_count": 1
}
```

| Status | Content / meaning |
| --- | --- |
| 200 | application/json — Confirmed result. |
| 400 | application/json — Invalid/missing credentials or no effective edit. |
| 413 | application/json — Request or received file exceeds the limit. |
| 422 | application/json — Invalid transfer input/save, transfer rejection, or persistence check failed. |
| 429 | application/json — Deployment request limit reached. |
| 500 | application/json — Unexpected service failure. |
| 502 | application/json — Remote outcome not confirmed; preserve available recovery bytes. |



- Requires an effective edit or unban_account/upload_items=true. False flags do not count as edits.

- enable_safety defaults to false; actual save-format and metadata bounds still apply. Unknown fields and invalid types are rejected rather than silently ignored.

- See TransferEditRequest in OpenAPI for every accepted top-level key and TRANSFERS.md for nested alternatives, aliases, and conversion rules.

- Consumes the original transfer and uploads the result to issue replacement codes. Changes are truncated at 1,000 entries; this transfer-edit response has no changes_truncated flag.



## Clone outcomes and recovery

A clone may return HTTP 201 even when only issuance-result persistence failed. In this case `persisted` is false, issued codes are present, and `issuance_id` is absent. Preserve the response; repeating the request can create another account.

```json
{
  "success": true,
  "persisted": false,
  "retry_safe": false,
  "template_id": "0123456789abcdef01234567",
  "order_id": "order-001",
  "attempt_id": "1123456789abcdef01234567",
  "created_at": "2026-09-04T00:00:00+00:00",
  "recovery_id": "2123456789abcdef01234567",
  "status": "issued",
  "transfer_code": "SAMPLE_TRANSFER",
  "confirmation_code": "1234",
  "message": "Codes issued, but result persistence failed. Save this response."
}
```

An unconfirmed clone returns HTTP 502. The current save may still equal the original, and `recovery_serialized` does not prove account creation succeeded.

```json
{
  "success": false,
  "retry_safe": false,
  "status": "needs_attention",
  "message": "New account creation was not confirmed.",
  "attempt_id": "1123456789abcdef01234567",
  "recovery_id": null,
  "backup_base64": "BASE64_OF_ORIGINAL_SAVE",
  "save_base64": "BASE64_OF_AVAILABLE_SAVE",
  "recovery_serialized": true
}
```

Use [TEMPLATES.md](TEMPLATES.md) for storage setup and order reservation, [TRANSFERS.md](TRANSFERS.md) for nested transfer inputs, and `/v2/features` for complete action-specific schemas.
