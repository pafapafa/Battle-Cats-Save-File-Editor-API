# API reference

Open the [deployed API documentation](https://battle-cats-save-file-editor-api.vercel.app/docs) for the English HTTP API reference. `/openapi.json` describes file, account, backup, and template endpoints, including authentication, request bodies, responses, and the arguments for registered editing actions.

## Documentation

| Reference | Contents |
| --- | --- |
| [README.md](README.md) | Vercel deployment, remote clients, file editing, and verification scope |
| [ACTIONS.md](ACTIONS.md) | All 89 action descriptions, required/optional arguments, ranges, defaults, operation examples, and source links |
| [ENDPOINTS.md](ENDPOINTS.md) | Categorized HTTP endpoints with authentication, request/response examples, and failure contracts |
| [FEATURES.md](FEATURES.md) | All 99 original source menu features, their API bindings, implementation status, and notes |
| [reference_features.json](reference_features.json) and `/v2/features` | Machine-readable menu mapping, action schemas, and source references |
| [TEMPLATES.md](TEMPLATES.md) | File backups, private JSONBin templates, copy issuance, and recovery |
| [TRANSFERS.md](TRANSFERS.md) | Transfer workflow contracts for `/edit` and `/info` |
| [EXAMPLES.md](EXAMPLES.md) | Python and other language clients, real request-file preparation, dependencies, and run commands |

## Browse by category

Use the endpoint reference for file inspection/editing, export/import/downloads, transfers and account operations, backups/templates, metadata, and service discovery. Use the action reference for the edits passed inside `operations`:

| Action category | Scope |
| --- | --- |
| Resources and inventory | Currency, tickets, upgrade materials, battle items, timers, and scheme rewards |
| Gacha seeds | Normal, rare, and event seeds |
| Cats, forms, talents, and orbs | Ownership, displayed levels, evolution, talents, guide flags, and orb counts |
| Storage and lineups | Stored cats/skills, equipped units, lineup names, active lineup, and unlocked slots |
| Base special skills | Displayed base/plus skill levels, random ranges, and metadata maxima |
| Story and event maps | Chapter progress, treasures, scores, outbreaks, legend/event categories, Aku, and Enigma |
| Gamatoto and Ototo | Expedition XP/helpers, engineers, construction materials, and cannons |
| Rewards and collections | Shrine, user-rank flags, medals, missions, enemy guide, and gambling resets |
| Account fields and save format | Local identity fields, pass state, play time, region, and format version |
| Explicit repairs | Targeted Gamatoto, Ototo, time, officer-pass, and equipment-menu resets |

Each action entry includes its actual argument schema and an example operation. Runtime notes cover constraints beyond the schema, such as valid IDs, metadata versions, conditional required fields, and effects on related progress.

The `/docs` reference offers Light, Dark, and System themes; the selected preference is stored in your browser. You can share a selected action with a link such as [the XP action](https://battle-cats-save-file-editor-api.vercel.app/docs#reference?view=actions&entry=items.xp). The hash format is `/docs#reference?view=actions&entry=<action-name>`.

## Backup API

| Request | Purpose |
| --- | --- |
| `POST /v1/templates` | Store a persistent original backup; returns `template_id` and a one-time `backup_token` |
| `GET /v1/templates` | Operator-only global list of stored template IDs |
| `GET /v1/templates/{id}` | Read backup metadata |
| `GET /v1/templates/{id}/download` | Download the original save bytes |
| `POST /v1/templates/{id}/clones` | Request a separate game account from the backup; requires JSON `order_id` |
| `POST /v1/backups` | Validate and return an uploaded file without cloud storage |

Editing and backup creation require no client API key. The JSONBin master key stays on the server. Send the one-time token returned at backup creation as `X-Backup-Token` when reading, downloading, or copying that backup. The optional `TEMPLATE_API_KEY` is only for operator-only global listings and metadata-cache deletion.

See [TEMPLATES.md](TEMPLATES.md) for request examples, record pagination, duplicate-order handling, and recovery behavior. Downloading a backup does not create a game account; the `/clones` request explicitly invokes account issuance.

## Limits and responses

- Raw save files: at most 1 MiB.
- HTTP request bodies: at most 2 MiB.
- Edit batches: 1 to 100 operations.
- Successful JSON file edits return the edited save, the original backup, persisted changes, and the output checksum.
- JSON edit responses include at most 1,000 change entries; `change_count` reports the full count. `output: "file"` returns only the edited binary attachment.

| Status | Meaning |
| --- | --- |
| `400` | Invalid request format |
| `403` | Operator-only route without the configured operator key |
| `404` | Requested record is unknown, or its backup token is missing or wrong |
| `413` | Request or save exceeds its size limit |
| `422` | Invalid edit, unsupported save, or values that cannot be persisted |
| `502` | A remote operation's result was not confirmed |
| `503` | Required configuration or storage is unavailable |
| `500` | An unexpected server failure; see the endpoint's response contract |

Inspect the JSON `message` when a request fails. Endpoint-specific preflight and remote-failure responses differ; [ENDPOINTS.md](ENDPOINTS.md) lists their fields. For account operations, `retry_safe: false` means the client must not automatically repeat issuance. Preserve any returned `backup_base64` and `save_base64` recovery data.

## File operations and transfers

Ordinary file inspection, editing, export, and import do not consume transfer codes. `/v2/save/from-transfer`, `/info`, and `/edit` include transfer reception. Reception uses the supplied transfer code; preserve the returned save because it can contain refreshed account credentials.

The API validates local save serialization and reports remote responses. Live game-account acceptance is not established by local file or transport tests.
