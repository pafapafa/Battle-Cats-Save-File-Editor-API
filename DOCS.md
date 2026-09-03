# API reference

Open `/docs` for the English HTTP API reference. `/openapi.json` describes file, account, backup, and template endpoints, including authentication, request bodies, responses, and the arguments for registered editing actions.

## Documentation

| Reference | Contents |
| --- | --- |
| [README.md](README.md) | Installation, file editing, deployment, and verification scope |
| [reference_features.json](reference_features.json) and `/v2/features` | Mapping of the 99 source menu entries, action schemas, and source references |
| [TEMPLATES.md](TEMPLATES.md) | File backups, private JSONBin templates, copy issuance, and recovery |
| [LEGACY.md](LEGACY.md) | Compatibility contracts for `/edit` and `/info` |
| [EXAMPLES.md](EXAMPLES.md) | Current Python clients and historical language examples |

## Backup API

| Request | Purpose |
| --- | --- |
| `POST /v1/templates` | Store a persistent original backup from multipart `file` or JSON `save_base64`; returns `template_id` |
| `GET /v1/templates` | List stored template IDs |
| `GET /v1/templates/{id}` | Read backup metadata |
| `GET /v1/templates/{id}/download` | Download the original save bytes |
| `POST /v1/templates/{id}/clones` | Request a separate game account from the backup; requires JSON `order_id` |
| `POST /v1/backups` | Validate and return an uploaded file without cloud storage |

Backup and template requests use `Authorization: Bearer <TEMPLATE_API_KEY>`. The JSONBin master key stays on the server. File-editor requests use `EDITOR_API_KEY`, falling back to `TEMPLATE_API_KEY` only when the editor key is not configured.

See [TEMPLATES.md](TEMPLATES.md) for request examples, record pagination, duplicate-order handling, and recovery behavior. Downloading a backup does not create a game account; the `/clones` request explicitly invokes account issuance.

## Limits and responses

- Raw save files: at most 1 MiB.
- HTTP request bodies: at most 2 MiB.
- Edit batches: 1 to 100 operations.
- Successful JSON file edits return the edited save, the original backup, persisted changes, and the output checksum.

| Status | Meaning |
| --- | --- |
| `400` | Invalid request format |
| `401` | Missing or incorrect authentication |
| `404` | Requested record or route not found |
| `413` | Request or save exceeds its size limit |
| `422` | Invalid edit, unsupported save, or values that cannot be persisted |
| `502` | A remote operation's result was not confirmed |
| `503` | Required configuration or storage is unavailable |

Inspect the JSON `message` when a request fails. For account operations, `retry_safe: false` means the client must not automatically repeat issuance. Preserve any returned `backup_base64` and `save_base64` recovery data.

## File operations and transfers

Ordinary file inspection, editing, export, and import do not consume transfer codes. `/v2/save/from-transfer`, legacy `/info`, and legacy `/edit` include transfer reception. Reception uses the supplied transfer code; preserve the returned save because it can contain refreshed account credentials.

The API validates local save serialization and reports remote responses. Live game-account acceptance is not established by local file or transport tests.
