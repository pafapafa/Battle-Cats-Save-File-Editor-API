# Examples

## Current Python clients

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

## Historical examples

The root examples with these extensions target the older API:

`.js`, `.ts`, `.go`, `.rs`, `.cpp`, `.cs`, `.c`, `.java`, `.kt`, `.swift`, `.php`, `.rb`, `.dart`, `.mojo`, `.sh`, `.ps1`.

They are retained as historical references. They have not been updated or verified as v2 clients. Build new clients from `/openapi.json`. To retain the legacy `/edit` route, add Bearer authentication and apply the strict input contracts in [LEGACY.md](LEGACY.md).
