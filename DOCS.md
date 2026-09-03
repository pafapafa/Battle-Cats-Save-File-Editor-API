# API reference

Open `/docs` for the Backups workspace, file editor, feature search, and action-specific schemas. `/openapi.json` describes the file, account, backup, and template endpoints, including the arguments for the registered editing actions.

## Documentation

| Reference | Contents |
| --- | --- |
| [README.md](README.md) | Installation, file editing, deployment, and verification scope |
| [reference_features.json](reference_features.json) and `/v2/features` | Mapping of the 99 source menu entries, action schemas, and source references |
| [TEMPLATES.md](TEMPLATES.md) | File backups, private JSONBin templates, copy issuance, and recovery |
| [LEGACY.md](LEGACY.md) | Compatibility contracts for `/edit` and `/info` |
| [EXAMPLES.md](EXAMPLES.md) | Current Python clients and historical language examples |

## Backups workspace

The default Backups view accepts a raw save file and detects its region. Use it to download a file backup, save a named private template, or inspect and download existing templates. Creating a copy from a template requests a separate game account and uses the issuance/recovery workflow described in [TEMPLATES.md](TEMPLATES.md).

Backup and template requests use `Authorization: Bearer <TEMPLATE_API_KEY>`. The JSONBin master key stays on the server. File-editor requests use `EDITOR_API_KEY`, falling back to `TEMPLATE_API_KEY` only when the editor key is not configured.

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
