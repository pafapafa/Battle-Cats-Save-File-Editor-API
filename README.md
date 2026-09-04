# BCSFE API

A Flask API for save-file backups, private templates, transfer workflows, and BCSFE editing. The vendored BCSFE implementation supplies the parser, serializer, game models, and version-specific field layouts.

API base URL: `https://battle-cats-save-file-editor-api.vercel.app`

The English [HTTP API reference](https://battle-cats-save-file-editor-api.vercel.app/docs) documents endpoints, authentication, request bodies, and responses. The [OpenAPI document](https://battle-cats-save-file-editor-api.vercel.app/openapi.json) provides machine-readable schemas, and the [feature inventory](https://battle-cats-save-file-editor-api.vercel.app/v2/features) lists action arguments, source references, and coverage.

## Documentation by task

| Reference | Use it for |
| --- | --- |
| [ACTIONS.md](ACTIONS.md) | All 89 save-edit actions, grouped into 13 categories, with arguments, defaults, examples, and source links |
| [ENDPOINTS.md](ENDPOINTS.md) | HTTP methods, authentication, request and response bodies, errors, and file/account/metadata routes |
| [FEATURES.md](FEATURES.md) | All 99 original BCSFE menu features, grouped by source menu, with API mappings and implementation limits |
| [TEMPLATES.md](TEMPLATES.md) | Persistent backups, original downloads, account-copy requests, record pagination, and recovery |
| [TRANSFERS.md](TRANSFERS.md) | Transfer inspection and editing with `/info` and `/edit`, including field aliases and recovery rules |
| [DOCS.md](DOCS.md) | Reference navigation, common limits, authentication, and transfer behavior |
| [EXAMPLES.md](EXAMPLES.md) | Python and 16 other language clients, request preparation, dependencies, and execution commands |

The action categories cover resources, gacha seeds, cats/forms/talents/orbs, storage, lineups, special skills, story, event/challenge maps, Gamatoto, Ototo, collection progress, account/save fields, and explicit repairs. Choose a category before selecting an action; its notes explain save-version and metadata requirements.

The API documentation supports Light, Dark, and System themes and saves the choice in your browser. Direct action links preserve the selected entry, for example [items.xp](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.xp).

## Deploy from GitHub to Vercel

1. Push this project to a GitHub repository and import that repository into Vercel.
2. Select the directory containing `main.py`, `requirements.txt`, and `vercel.json` as the project root.
3. Configure the environment variables below for the deployment environment, then deploy. Redeploy after changing environment variables.
4. Open `/docs` on the deployment URL and use its HTTP endpoints from your application or API client.

| Environment variable | Purpose |
| --- | --- |
| `EDITOR_API_KEY` | Bearer key for file editing; falls back to `TEMPLATE_API_KEY` when absent |
| `TEMPLATE_API_KEY` | Bearer key for backup and template routes; at least 32 characters |
| `JSONBIN_API_KEY` | Existing JSONBin master key for private template storage |
| `TEMPLATE_ENCRYPTION_KEY` | Optional explicit template encryption key; otherwise derived from the JSONBin key |

The deployment entry point is the Flask `app` in `main.py`, using `vercel.json` routing. Metadata and configuration caches use temporary storage. Environment variables take precedence over the local, gitignored `template_secrets.py` configuration; that file is excluded from Git deployment. See [TEMPLATES.md](TEMPLATES.md) for storage setup and recovery details.

Check the project's function duration against metadata downloads and remote operations. Runtime requirements and limits are documented in Vercel's [Python runtime documentation](https://vercel.com/docs/functions/runtimes/python) and [function limits](https://vercel.com/docs/functions/limitations). Repository test results and deployed behavior are verified separately.

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

[ENDPOINTS.md](ENDPOINTS.md) documents the full HTTP contracts. [DOCS.md](DOCS.md) lists shared input limits and error handling; [TRANSFERS.md](TRANSFERS.md) documents the `/info` and `/edit` transfer workflows.

## Python clients

[cli.py](cli.py) and [example.py](example.py) run on the caller's computer and send HTTPS requests to the deployed v2 API. They preserve the input file and refuse to overwrite an existing output file.

```powershell
$env:EDITOR_API_KEY = 'the-key-configured-on-your-server'
py -m pip install requests
py cli.py features
py cli.py inspect original.save --country kr
py cli.py edit original.save operations.json edited.save --country kr
```

`operations.json` contains the `operations` array from the request above. The default API origin is `https://battle-cats-save-file-editor-api.vercel.app`; use `--url` before the command to select another deployment. These commands run an API client. The 16 other language clients accept a complete request JSON file and an output save path; [EXAMPLES.md](EXAMPLES.md) documents their shared contract and build/run commands.

## Coverage and verification

The feature inventory maps 79 game-editing menu entries to 89 typed actions and records the disposition of all 99 unique source menu entries. [FEATURES.md](FEATURES.md) provides the readable category-by-category mapping; [reference_features.json](reference_features.json) and `/v2/features` expose its structured form. [ACTIONS.md](ACTIONS.md) gives an example for every registered action.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:BCSFE_TEST_REAL_METADATA = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_editor_real_metadata.py -v
```

Ordinary tests do not contact game account servers. The opt-in suite uses public kr 15.5.0 metadata and generated save files to verify representative edits through the binary validation boundary. Registered actions also have binary and HTTP execution examples. Separate regional checks covered kr, en, jp, and tw 15.5.0 metadata and representative cat edits. These checks do not establish compatibility with every game version, account, or input combination.

Game-account operations have tests for simulated success, failure, and recovery responses. Live account creation, transfer, and in-game acceptance remain separate verification steps.

Four device operations involving ADB/root or restarting the game are unavailable on Vercel. Two terminal-only theme/exit entries do not apply to HTTP. Save paths, region conversion, configuration, and game-data management have HTTP equivalents where applicable. This project does not claim identical behavior for the entire interactive CLI.

## Source and license

Original project: BCSFE by fieryhenry. The runtime in `vendor/bcsfe` preserves the original parser's executable behavior. Comments and docstrings have been removed and blank lines normalized, so the runtime files are not byte-identical to the upstream source. [SOURCE_MANIFEST.json](vendor/bcsfe/SOURCE_MANIFEST.json) records `upstream_sha256` for the supplied original and `sha256` for the current file. Installation uses the vendored runtime.

The GNU GPL-3.0-or-later license and original `LICENSE` are retained.
