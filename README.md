# BCSFE API

A Flask API for save-file backups, private templates, and BCSFE editing. The project uses the supplied BCSFE source in `vendor/bcsfe`; it does not reimplement the save parser or its field offsets.

The English HTTP API reference is available at `/docs`. It documents endpoints, authentication, request bodies, and responses. Machine-readable schemas are available at `/openapi.json`.

## Run locally

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:EDITOR_API_KEY = 'replace-with-a-server-key-of-at-least-32-characters'
.\.venv\Scripts\python.exe main.py
```

Open `http://127.0.0.1:5000/docs`. The OpenAPI document is at `/openapi.json`; action arguments, source references, and feature coverage are at `/v2/features`.

File editing accepts `EDITOR_API_KEY`, falling back to `TEMPLATE_API_KEY` when the editor key is not configured. Backup and template routes use `TEMPLATE_API_KEY`. Private cloud templates also require `JSONBIN_API_KEY`. Environment variables take precedence over the local, gitignored `template_secrets.py` configuration. See [TEMPLATES.md](TEMPLATES.md) for setup and recovery details.

## Backup and copy APIs

Store a persistent backup with `POST /v1/templates`, using Bearer authentication and either a multipart `file` or JSON `save_base64`. The response returns a `template_id`. List stored backups with `GET /v1/templates`, inspect one with `GET /v1/templates/{id}`, and retrieve its original bytes with `GET /v1/templates/{id}/download`.

`POST /v1/backups` validates and returns the uploaded file without storing it in JSONBin. For a separate game account based on a stored template, call `POST /v1/templates/{id}/clones` with an `order_id` in the JSON body. This is an account-issuance operation, distinct from downloading the original. Live account creation and transfer acceptance require separate verification.

See [TEMPLATES.md](TEMPLATES.md) for request examples, storage configuration, duplicate-order handling, and recovery responses. Downloaded save files require a separate import or transfer workflow to restore them inside the game.

## Edit a file

Send an authenticated request to `POST /v2/save/edit`:

```json
{
  "country_code": "kr",
  "save_base64": "BASE64_OF_THE_ORIGINAL_SAVE",
  "operations": [
    {"action": "items.xp", "args": {"value": 99999999}},
    {"action": "gatya.rare_seed", "args": {"value": 4294967295}}
  ]
}
```

Use `Authorization: Bearer <EDITOR_API_KEY>`, or the configured template key when the editor key is absent. The JSON response includes `save_base64` for the edited file, `backup_base64` for the original, persisted `changes`, and `sha256`.

Operations run on a copy. The API serializes and reparses the result, checks its checksum and binary stability, and verifies that the requested values survived serialization before returning success. Failed batches are not returned as partially successful edits. Unrequested tutorial, pass, lineup, and Gamatoto skin changes are not applied automatically.

Actions that expose `respect_maxima` apply BCSFE's recommended limits by default. Setting it to `false` does not bypass the storage field's integer range. Cat IDs and array indexes are zero-based. Displayed levels, forms, and map crowns follow the individual action schemas. Supported level ranges use `{ "min": 10, "max": 20 }`.

## API reference

| Area | Routes |
| --- | --- |
| File inspection and editing | `/v2/save/inspect`, `/v2/save/edit` |
| JSON export, import, and file download | `/v2/save/export`, `/v2/save/import`, `/v2/save/download` |
| Transfer reception and upload | `/v2/save/from-transfer`, `/v2/save/upload` |
| Account operations | `/v2/account/new`, `/v2/account/convert-region`, `/v2/account/upload-items` |
| File backup and private templates | `/v1/backups`, `/v1/templates`; see [TEMPLATES.md](TEMPLATES.md) |
| Game metadata | `/v2/metadata/versions`, `/v2/metadata/prepare`, `/v2/metadata/cache` |

Ordinary file editing does not consume transfer codes. Transfer reception does: retain the returned save containing refreshed credentials. Server-side authentication failures do not automatically create a replacement account; account creation requires an explicit request.

[DOCS.md](DOCS.md) lists input limits and error handling. [LEGACY.md](LEGACY.md) documents the compatibility routes.

## Python clients

[cli.py](cli.py) and [example.py](example.py) use the v2 file API. They refuse to overwrite an input file or an existing output file.

```powershell
$env:EDITOR_API_KEY = 'the-key-configured-on-your-server'
.\.venv\Scripts\python.exe cli.py features
.\.venv\Scripts\python.exe cli.py inspect original.save --country kr
.\.venv\Scripts\python.exe cli.py edit original.save operations.json edited.save --country kr
```

`operations.json` contains the `operations` array from the request above. The default API origin is local; use `--url` before the command to select a deployed server. See [EXAMPLES.md](EXAMPLES.md) for export/import commands and the status of older language examples.

## Coverage and verification

The feature inventory maps 79 game-editing menu entries to 89 typed actions and records the disposition of all 99 unique source menu entries. [reference_features.json](reference_features.json) and `/v2/features` provide the detailed mapping.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:BCSFE_TEST_REAL_METADATA = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_editor_real_metadata.py -v
```

Ordinary tests do not contact game account servers. The opt-in suite uses public kr 15.5.0 metadata and generated save files to verify representative edits through the binary validation boundary. Registered actions also have binary and HTTP execution examples. Separate regional checks covered kr, en, jp, and tw 15.5.0 metadata and representative cat edits. These checks do not establish compatibility with every game version, account, or input combination.

Game-account operations have tests for simulated success, failure, and recovery responses. Live account creation, transfer, and in-game acceptance remain separate verification steps.

Four device operations involving ADB/root or restarting the game are unavailable on Vercel. Two terminal-only theme/exit entries do not apply to HTTP. Save paths, region conversion, configuration, and game-data management have HTTP equivalents where applicable. This project does not claim identical behavior for the entire interactive CLI.

## Vercel

The deployment entry point is the Flask `app` in `main.py`, using `vercel.json` routing. Metadata and configuration caches use temporary storage. Configure `EDITOR_API_KEY` or `TEMPLATE_API_KEY` for editing, and `TEMPLATE_API_KEY` plus `JSONBIN_API_KEY` for private templates. The local `template_secrets.py` file is excluded from Git deployment.

Check the project's function duration against metadata downloads and remote operations. Runtime requirements and limits are documented in Vercel's [Python runtime documentation](https://vercel.com/docs/functions/runtimes/python) and [function limits](https://vercel.com/docs/functions/limitations). Local test results and deployed behavior are verified separately.

## Source and license

Original project: BCSFE by fieryhenry. The supplied source is retained in `vendor/bcsfe`; [SOURCE_MANIFEST.json](vendor/bcsfe/SOURCE_MANIFEST.json) records its SHA-256 hashes. Installation uses this source rather than relying on a matching PyPI version label.

The GNU GPL-3.0-or-later license and original `LICENSE` are retained.
