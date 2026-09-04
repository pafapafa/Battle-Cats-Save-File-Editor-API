# Backups and private account templates

A backup preserves the original save file. A private template stores that file in JSONBin so it can be downloaded later or used to request a separate game account with the same starting progress.

API base URL: `https://battle-cats-save-file-editor-api.vercel.app`. The [HTTP API reference](https://battle-cats-save-file-editor-api.vercel.app/docs) and [ENDPOINTS.md](ENDPOINTS.md) document the route contracts. For edits to a downloaded file, use the categorized [action reference](ACTIONS.md); [FEATURES.md](FEATURES.md) maps the original BCSFE menus.

The file workflow uses raw saves produced by BCSFE. It does not call the `/edit` handler. Downloads provide recovery files; they do not automatically restore data inside the game app.

## HTTP workflow

1. Send `POST /v1/templates` with a raw multipart `file` or JSON `save_base64`. An optional name labels the backup; `country_code: "auto"` detects its region from the checksum. The API stores the original and returns `template_id`.
2. Use `GET /v1/templates` to list stored templates and `GET /v1/templates/{id}` to inspect one.
3. Use `GET /v1/templates/{id}/download` to retrieve the original save bytes.
4. To request a separate game account from a template, send `POST /v1/templates/{id}/clones` with JSON `order_id`. The API records an attempt before the remote operation, then stores recovery and issuance records as those steps succeed.

`POST /v1/backups` provides a separate nonpersistent operation: it validates and returns the uploaded original without storing it in JSONBin. All these operations are HTTP APIs; `/docs` provides their reference documentation.

If starting from a transfer code, first receive the save through `/v2/save/from-transfer`. Reception uses that code. Register the returned save containing refreshed credentials as the template and retain the original/recovery files returned by the API.

Copy issuance uses the supplied BCSFE account-creation implementation. Automated tests cover simulated server responses and recovery behavior; live account creation, login, and transfer acceptance require separate verification. File-editing coverage is documented at `/v2/features` and in [README.md](README.md).

## Vercel configuration

Import the GitHub repository into Vercel and configure these values in the project's environment settings before deployment. Redeploy after changing them.

| Setting | Purpose |
| --- | --- |
| `TEMPLATE_API_KEY` | Bearer key for backup, template, and issuance routes; at least 32 characters |
| `JSONBIN_API_KEY` | Existing JSONBin master key, required for cloud storage |
| `TEMPLATE_ENCRYPTION_KEY` | Optional explicit encryption key; otherwise derived from the JSONBin key |

Environment variables override the local `template_secrets.py` values. Existing local credentials remain usable. The template store creates new private bins; it does not update the existing user, code, or cat database bins.

Retain the key used to encrypt stored records so they remain readable. `template_secrets.py` is excluded from Git deployment. Clients send the template API key in `Authorization`; they do not need the JSONBin master key.

## Store a template through the API

All `/v1` routes below require `Authorization: Bearer <TEMPLATE_API_KEY>`.

```python
import os
import requests

base = "https://battle-cats-save-file-editor-api.vercel.app"
headers = {"Authorization": "Bearer " + os.environ["TEMPLATE_API_KEY"]}

with open("account.save", "rb") as file:
    response = requests.post(
        base + "/v1/templates",
        headers=headers,
        files={"file": file},
        data={"name": "Starter account", "country_code": "auto"},
        timeout=120,
    )
response.raise_for_status()
template_id = response.json()["template_id"]
```

JSON requests may supply `save_base64`, `name`, and `country_code` instead of a multipart file. The upload fields are:

| Field | Required | Meaning and default |
| --- | --- | --- |
| `file` / `save_base64` | Yes | A raw multipart save or standard Base64 JSON value; 32 bytes to 1 MiB |
| `name` | No | Defaults to `Backup`; leading/trailing whitespace is removed, then 1..100 characters are required |
| `country_code` | No | Defaults to `kr` for existing clients; `auto` detects the checksum region, or specify `kr`, `en`, `jp`, or `tw` |

An explicitly selected region must match the file. Stored and returned metadata always uses the detected `kr`, `en`, `jp`, or `tw` value, never `auto`.

Creation returns **201** with metadata and no save payload. A representative response shape is shown below; IDs, digest, and file metadata are illustrative:

```json
{
  "success": true,
  "template_id": "111111111111111111111111",
  "name": "Starter account",
  "country_code": "kr",
  "game_version": 150500,
  "bytes": 1024,
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "created_at": "2026-09-04T00:00:00+00:00",
  "clone_ready": true
}
```

`GET /v1/templates/{id}` returns the same metadata fields with **200**. Use the download route to obtain bytes; metadata responses do not contain `save_base64`.

Records are compressed and encrypted. Large records are divided among smaller private bins, and a template ID is returned only after all required parts are stored. Downloaded originals are checked against their recorded SHA-256 checksum.

`clone_ready` records whether the library reproduced the original bytes at upload time. A false result still permits storage and download. Each clone request repeats the load/save equality check using the current library and is blocked if that check fails; the stored flag alone does not authorize issuance or establish game-server acceptance.

## Download a stored original

Use the `template_id` returned by the storage request:

```python
response = requests.get(
    base + "/v1/templates/" + template_id + "/download",
    headers=headers,
    timeout=120,
)
response.raise_for_status()
with open("downloaded-backup.save", "xb") as file:
    file.write(response.content)
```

The response is the original binary save. This request does not create an account or issue transfer codes.

## Routes

| Method and path | Behavior |
| --- | --- |
| `POST /v1/backups` | Download the uploaded original; no JSONBin storage |
| `POST /v1/templates` | Store an original and return `template_id` |
| `GET /v1/templates` | List template IDs |
| `GET /v1/templates/{id}` | Read name, region, version, checksum, and readiness |
| `GET /v1/templates/{id}/download` | Download the original save |
| `POST /v1/templates/{id}/clones` | Request a separate account; JSON body requires `order_id` |
| `GET /v1/issuances/{id}` | Read a stored issuance result and transfer codes |
| `GET /v1/template-records?kind=issuance` | List records; `kind` accepts `attempt`, `issuance`, or `recovery` |
| `GET /v1/attempts/{id}` | Read an issuance-start record |
| `GET /v1/recoveries/{id}` | Read recovery record order/template metadata |
| `GET /v1/recoveries/{id}/download` | Download the new account's recovery save |

## List and paginate records

`GET /v1/templates` returns IDs and JSONBin creation times. It does not include full template metadata:

```json
{
  "success": true,
  "templates": [
    {"template_id": "111111111111111111111111", "created_at": null}
  ],
  "next_cursor": null
}
```

`created_at` is a string when available and may be `null` in a listing. Omit `cursor` or use an empty string for the first request; pass `next_cursor` unchanged on later requests. A filtered page may be empty while another underlying JSONBin page exists, so continue until `next_cursor` is `null`:

```python
cursor = ""
template_ids = []
while True:
    response = requests.get(
        base + "/v1/templates",
        headers=headers,
        params={"cursor": cursor},
        timeout=120,
    )
    response.raise_for_status()
    page = response.json()
    template_ids.extend(item["template_id"] for item in page["templates"])
    cursor = page["next_cursor"]
    if cursor is None:
        break
```

`GET /v1/template-records?kind=issuance` follows the same pagination rules but returns `records` entries with `id` and `created_at`. `kind` defaults to `issuance` and also accepts `attempt` or `recovery`. There is no server-side `order_id` filter; retrieve each relevant record to inspect its order. Record IDs and nonempty cursors are 24 hexadecimal characters.

## Copy issuance and duplicate orders

Send `POST /v1/templates/{id}/clones` with the template Bearer key and a JSON body:

```json
{"order_id": "order-2026-0001"}
```

`order_id` accepts 1 to 100 characters: letters, numbers, `_`, `.`, `:`, or `-`.

A copy request loads a fresh save from the immutable template. The account transport requires acknowledgments for account creation and synchronization of cat food and rare/platinum/legend ticket balances. The API checks that the account identifier changed, stores a pre-transfer recovery snapshot, and then requests transfer codes. This is not an independent readback of every account field or proof of in-game acceptance. Authentication failure alone does not trigger automatic account creation.

A confirmed issuance returns **201**. This response shape uses illustrative IDs and codes:

```json
{
  "success": true,
  "persisted": true,
  "retry_safe": false,
  "issuance_id": "444444444444444444444444",
  "template_id": "111111111111111111111111",
  "order_id": "order-2026-0001",
  "attempt_id": "222222222222222222222222",
  "recovery_id": "333333333333333333333333",
  "created_at": "2026-09-04T00:00:00+00:00",
  "status": "issued",
  "transfer_code": "EXAMPLE_TRANSFER_CODE",
  "confirmation_code": "EXAMPLE_CONFIRMATION_CODE"
}
```

If only final issuance-record storage fails, the response is still **201**, with `persisted: false`, a `message`, and no `issuance_id`. The codes already exist; store the complete response. Successful clone responses contain codes and record IDs, not save bytes. Download the pre-transfer recovery snapshot separately through `/v1/recoveries/{recovery_id}/download`.

`order_id` identifies a request for tracking. **It is not an idempotency key.** JSONBin does not provide the atomic order reservation required to coordinate concurrent issuers. Sending the same clone request twice can create two accounts.

For vending or order-processing services, use the `issue_once` example in [examples/vending_backend.py](examples/vending_backend.py):

```python
import os
from examples.vending_backend import issue_once

result = issue_once(
    api_url="https://battle-cats-save-file-editor-api.vercel.app",
    token=os.environ["TEMPLATE_API_KEY"],
    template_id=product["template_id"],
    order_id=order["id"],
    db_path="data/template-orders.sqlite",
)
```

The example reserves an order in a persistent SQLite database before calling the API. Concurrent requests share that reservation. A completed order reuses its saved result; an uncertain result does not trigger another issuance. Store the result before delivering it to a customer.

All workers must use the same persistent order database. A Vercel temporary directory is unsuitable for this SQLite file. For workers on multiple machines, implement the same unique-order reservation in the service's transactional database.

## Failures and recovery

The workflow stores an attempt before contacting the game server, a recovery save after confirmed account creation/synchronization, and an issuance record after transfer codes are returned.

- Preflight failures return `{"success": false, "message": "..."}`: `400` for invalid input, `401` for authentication, `404` for missing/wrong records, `422` for invalid or unstable saves, and `503` for required configuration/storage failures. If attempt storage fails, the account call has not begun.
- A failure after the attempt is stored returns `502` with `success: false`, `retry_safe: false`, `status: "needs_attention"`, `message`, `attempt_id`, nullable `recovery_id`, `backup_base64`, `save_base64`, and `recovery_serialized`. This failure response does not contain `order_id`, `template_id`, issued codes, or `persisted`; keep the original request context with it.
- `started` on an attempt records that work began; it is not a final success state. Check the issuance record for the final stored result.
- If only issuance-result storage fails, the response can include issued codes with `persisted: false`. Preserve that response in the order database.
- Preserve returned `backup_base64` and `save_base64` even when recovery-bin storage fails. They contain the original and the available recovery save.
- `recovery_serialized: true` means the in-memory state could be serialized; it can still be the original account. If false, `save_base64` falls back to the original bytes. Neither value confirms successful account creation.
- A timeout, disconnection, or `needs_attention` result requires record review, not automatic reissuance. Use the record list to find attempts, issuances, and recovery saves for the order.

Game-server operations and JSONBin writes are not one transaction. A process can stop after an account or code is created but before its record is stored. In that case, do not infer success or retry under a new order ID. Private record and download responses use `Cache-Control: no-store`.

| Record endpoint | Returned information |
| --- | --- |
| `/v1/attempts/{id}` | Immutable `started` marker with attempt/template/order IDs and creation time |
| `/v1/recoveries/{id}` | Recovery/template/order/attempt IDs, creation time, region, and SHA-256; no save payload |
| `/v1/recoveries/{id}/download` | Raw pre-transfer recovery save bytes |
| `/v1/issuances/{id}` | Stored issuance/template/order/attempt/recovery IDs, creation time, `issued` status, and transfer codes |

Stored issuance retrieval does not repeat the immediate clone response's `persisted` or `retry_safe` fields. The attempt marker is never updated to a final status; use issuance and recovery records to investigate the order.

## Verification

Automated tests cover original-byte preservation, unrelated-field preservation, authentication, input validation, encryption tampering, split records, failure reporting, and order reservation behavior under repeat requests, concurrency, and timeouts. A private-bin storage/read check used the existing JSONBin account and removed only its test bins. It did not use a real game account.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

JSONBin references: [private bin creation](https://jsonbin.io/api-reference/bins/create), [paginated bin listing](https://jsonbin.io/api-reference/collections/bins/uncategorized), and [document updates](https://jsonbin.io/api-reference/bins/update).
