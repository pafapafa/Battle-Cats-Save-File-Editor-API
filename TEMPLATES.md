# Backups and private account templates

A backup preserves the original save file. A private template stores that file in JSONBin so it can be downloaded later or used to request a separate game account with the same starting progress.

The file workflow uses raw saves produced by BCSFE. It does not call the legacy `/edit` handler. Downloads provide recovery files; they do not automatically restore data inside the game app.

## HTTP workflow

1. Send `POST /v1/templates` with a raw multipart `file` or JSON `save_base64`, plus a name and region. The API stores the original and returns `template_id`.
2. Use `GET /v1/templates` to list stored templates and `GET /v1/templates/{id}` to inspect one.
3. Use `GET /v1/templates/{id}/download` to retrieve the original save bytes.
4. To request a separate game account from a template, send `POST /v1/templates/{id}/clones` with JSON `order_id`. This produces issuance and recovery records.

`POST /v1/backups` provides a separate nonpersistent operation: it validates and returns the uploaded original without storing it in JSONBin. All these operations are HTTP APIs; `/docs` provides their reference documentation.

If starting from a transfer code, first receive the save through `/v2/save/from-transfer`. Reception uses that code. Register the returned save containing refreshed credentials as the template and retain the original/recovery files returned by the API.

Copy issuance uses the supplied BCSFE account-creation implementation. Automated tests cover simulated server responses and recovery behavior; live account creation, login, and transfer acceptance require separate verification. File-editing coverage is documented at `/v2/features` and in [README.md](README.md).

## Configuration

| Setting | Purpose |
| --- | --- |
| `TEMPLATE_API_KEY` | Bearer key for backup, template, and issuance routes; at least 32 characters |
| `JSONBIN_API_KEY` | Existing JSONBin master key, required for cloud storage |
| `TEMPLATE_ENCRYPTION_KEY` | Optional explicit encryption key; otherwise derived from the JSONBin key |

Environment variables override the local `template_secrets.py` values. Existing local credentials remain usable. The template store creates new private bins; it does not update the existing user, code, or cat database bins.

Retain the key used to encrypt stored records so they remain readable. `template_secrets.py` is excluded from Git. For a Vercel Git deployment, configure the required values in the project's environment settings. Clients send the template API key in `Authorization`; they do not need the JSONBin master key.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app main run
```

## Store a template through the API

All `/v1` routes below require `Authorization: Bearer <TEMPLATE_API_KEY>`.

```python
import os
import requests

base = "http://127.0.0.1:5000"
headers = {"Authorization": "Bearer " + os.environ["TEMPLATE_API_KEY"]}

with open("account.save", "rb") as file:
    response = requests.post(
        base + "/v1/templates",
        headers=headers,
        files={"file": file},
        data={"name": "Starter account", "country_code": "kr"},
        timeout=120,
    )
response.raise_for_status()
template_id = response.json()["template_id"]
```

JSON requests may supply `save_base64`, `name`, and `country_code` instead of a multipart file. Saves are limited to 1 MiB. Supported regions are `kr`, `en`, `jp`, and `tw`.

Records are compressed and encrypted. Large records are divided among smaller private bins, and a template ID is returned only after all required parts are stored. Downloaded originals are checked against their recorded SHA-256 checksum.

A template with `clone_ready: false` can still be stored and downloaded, but copy issuance is blocked. This flag means the current library could not reproduce the original bytes through a stable load/save round trip.

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

Lists follow JSONBin pagination. A filtered page can be empty while `next_cursor` is present. Continue with `cursor=<next_cursor>` until `next_cursor` is `null`.

## Copy issuance and duplicate orders

Send `POST /v1/templates/{id}/clones` with the template Bearer key and a JSON body:

```json
{"order_id": "order-2026-0001"}
```

`order_id` accepts 1 to 100 characters: letters, numbers, `_`, `.`, `:`, or `-`.

A copy request loads a fresh save from the immutable template. The API checks that the account identifier changed, confirms account creation and managed-item synchronization, stores recovery data, and then requests transfer codes. Authentication failure alone does not trigger automatic account creation.

`order_id` identifies a request for tracking. **It is not an idempotency key.** JSONBin does not provide the atomic order reservation required to coordinate concurrent issuers. Sending the same clone request twice can create two accounts.

For vending or order-processing services, use the `issue_once` example in [examples/vending_backend.py](examples/vending_backend.py):

```python
import os
from examples.vending_backend import issue_once

result = issue_once(
    api_url="https://your-project.vercel.app",
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

- `started` on an attempt records that work began; it is not a final success state. Check the issuance record for the final stored result.
- If only issuance-result storage fails, the response can include issued codes with `persisted: false`. Preserve that response in the order database.
- Preserve returned `backup_base64` and `save_base64` even when recovery-bin storage fails. They contain the original and the available recovery save.
- `recovery_serialized: false` means the new state could not be serialized. Do not treat it as a successful recoverable result.
- A timeout, disconnection, or `needs_attention` result requires record review, not automatic reissuance. Use the record list to find attempts, issuances, and recovery saves for the order.

Game-server operations and JSONBin writes are not one transaction. A process can stop after an account or code is created but before its record is stored. In that case, do not infer success or retry under a new order ID. Private record and download responses use `Cache-Control: no-store`.

## Verification

Automated tests cover original-byte preservation, unrelated-field preservation, authentication, input validation, encryption tampering, split records, failure reporting, and order reservation behavior under repeat requests, concurrency, and timeouts. A private-bin storage/read check used the existing JSONBin account and removed only its test bins. It did not use a real game account.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

JSONBin references: [private bin creation](https://jsonbin.io/api-reference/bins/create), [paginated bin listing](https://jsonbin.io/api-reference/collections/bins/uncategorized), and [document updates](https://jsonbin.io/api-reference/bins/update).
