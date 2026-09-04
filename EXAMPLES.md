# Examples

## Python clients

[`cli.py`](cli.py) and [`example.py`](example.py) run on the caller's computer and call the authenticated v2 API at `https://battle-cats-save-file-editor-api.vercel.app` by default. Set `EDITOR_API_KEY`, or `TEMPLATE_API_KEY` when it is the server's configured editor fallback. The commands below are remote API client operations.

```powershell
$env:EDITOR_API_KEY = 'the-key-configured-on-your-server'
py -m pip install requests
py cli.py features
py cli.py inspect original.save --country kr
py cli.py edit original.save operations.json edited.save --country kr
py cli.py export original.save state.json --country kr
py cli.py import state.json restored.save
```

To specify the deployment URL explicitly, place `--url` before the command. Replace this URL when using your own deployment:

```powershell
py cli.py --url https://battle-cats-save-file-editor-api.vercel.app inspect original.save --country kr
```

`operations.json` contains an array of action requests:

```json
[
  {"action": "items.xp", "args": {"value": 1000}}
]
```

Use `/v2/features` for valid action names and arguments. `example.py` provides a small bytes-in/file-out example; review its `OPERATIONS` list before running it.

Both clients preserve the input file and refuse to overwrite an existing output. They stop on HTTP errors or invalid save responses. Inspection prints file metadata without printing the account state. Neither client receives transfer codes, creates accounts, or uploads saves to the game server.

## Template issuance example

[`examples/vending_backend.py`](examples/vending_backend.py) demonstrates server-side order processing for JSONBin template issuance. It reserves each order in a persistent SQLite database before requesting a copy and reuses a stored successful result. See [TEMPLATES.md](TEMPLATES.md) for database requirements and uncertain-result handling.

## Shared request-file clients

The other 16 language clients call `POST /v2/save/edit` with the same interface:

```text
CLIENT REQUEST_JSON OUTPUT_SAVE
```

`REQUEST_JSON` is an existing UTF-8 JSON file containing `country_code`, `save_base64`, `operations`, and `"output": "file"`. The clients send those JSON bytes to the API and save a successful binary response at `OUTPUT_SAVE`. They reject an existing output path, HTTP errors, redirects, and a nonbinary response. They do not receive game transfers or request new accounts.

Set `EDITOR_API_KEY`, or `TEMPLATE_API_KEY` when used as the server's editor fallback. `BCSFE_API_URL` optionally selects another API origin; the default is `https://battle-cats-save-file-editor-api.vercel.app`. API keys are read from the environment. The `cli.py` and `example.py` commands above retain their file-oriented interface and `--url` option.

### Prepare a request from a real save

Run this Python snippet in the project directory with an existing `original.save`. Change the region and requested operations as needed. Python's standard library is sufficient:

```python
import base64
import json
from pathlib import Path

original = Path("original.save")
payload = {
    "country_code": "kr",
    "save_base64": base64.b64encode(original.read_bytes()).decode("ascii"),
    "operations": [{"action": "items.xp", "args": {"value": 1000}}],
    "output": "file",
}
with Path("request.json").open("x", encoding="utf-8") as file:
    json.dump(payload, file, ensure_ascii=False)
```

This preserves the original file and refuses to overwrite an existing request file. The request contains the full save, including its account state. Use [ACTIONS.md](ACTIONS.md) for other operations and keep the request with the same access controls as the save. The API accepts saves up to 1 MiB and request bodies up to 2 MiB.

### Interpreted clients

Run these commands from the project directory after installing the indicated runtime:

| Language | Runtime and dependencies | Command |
| --- | --- | --- |
| JavaScript | Node.js 24+; standard library | `node example.js request.json edited.save` |
| TypeScript | Node.js 24+ native TypeScript support; no npm packages | `node example.ts request.json edited.save` |
| PHP | PHP 8+ with the cURL extension | `php example.php request.json edited.save` |
| Ruby | Ruby 3.1+; standard library | `ruby example.rb request.json edited.save` |
| Dart | Dart 3.13+; SDK standard libraries | `dart run example.dart request.json edited.save` |
| Mojo | Mojo 1.0 with a compatible CPython shared library and Python standard library | `mojo example.mojo request.json edited.save` |
| Bash | Bash 4+ and curl | `bash example.sh request.json edited.save` |
| PowerShell | PowerShell 7.4+ | `pwsh -File example.ps1 request.json edited.save` |

### Compiled clients

Choose a distinct output save path for each run. The commands below use the same `request.json` prepared above.

| Language | Runtime and dependencies | Build/run |
| --- | --- | --- |
| C | C11 compiler and libcurl development headers/library | `gcc -std=c11 example.c -lcurl -o example-c`, then `./example-c request.json edited.save` |
| C++ | C++17 compiler and libcurl development headers/library | `g++ -std=c++17 example.cpp -lcurl -o example-cpp`, then `./example-cpp request.json edited.save` |
| Java | JDK 11+ | `java example.java request.json edited.save` |
| Kotlin | Kotlin compiler and JVM 11+ | `kotlinc example.kt -jvm-target 11 -include-runtime -d example-kotlin.jar`, then `java -jar example-kotlin.jar request.json edited.save` |
| Go | Go 1.16+; standard library | `go run example.go request.json edited.save` |
| C# | .NET 10 SDK file-based app support | `dotnet run --file example.cs -- request.json edited.save` |
| Rust | Rust/Cargo with reqwest; manifest below | `cargo run -- request.json edited.save` |
| Swift | Swift 5.7+; Foundation and FoundationNetworking where applicable | `swift example.swift request.json edited.save` |

For Rust, place this `Cargo.toml` alongside `example.rs`:

```toml
[package]
name = "bcsfe-api-client"
version = "0.1.0"
edition = "2021"

[[bin]]
name = "bcsfe-api-client"
path = "example.rs"

[dependencies]
reqwest = { version = "0.12", default-features = false, features = ["blocking", "rustls-tls"] }
```

Runtime availability and build verification differ by environment. The request contract is shared; game-version support and metadata requirements are enforced by the API for the submitted save. The client examples do not establish live game-account acceptance.

## Transfer clients

Use the HTTP request fields in [TRANSFERS.md](TRANSFERS.md) to build a client for `/info` or `/edit`. These endpoints consume the supplied transfer code. [ENDPOINTS.md](ENDPOINTS.md) documents the full successful and recovery responses, including when an automatic retry is unsafe.
