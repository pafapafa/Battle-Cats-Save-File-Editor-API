from flask import Flask, request, jsonify
import time
from collections import defaultdict, deque
from patcher import (
    download_ponos_save,
    patch_and_upload_save,
    INT32_MAX,
)

app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

IP_MINUTE_HISTORY = defaultdict(deque)
IP_DAILY_HISTORY = defaultdict(deque)

MINUTE_WINDOW = 60
DAILY_WINDOW = 86400

MAX_PER_MINUTE = 10
MAX_PER_DAY = 100


def get_client_ip() -> str:
    xf = request.headers.get("X-Forwarded-For")
    if xf:
        return xf.split(",")[0].strip()
    xr = request.headers.get("X-Real-IP")
    if xr:
        return xr.strip()
    return request.remote_addr or "127.0.0.1"


@app.before_request
def handle_rate_limits():
    if request.method == "OPTIONS":
        return

    client_ip = get_client_ip()
    now = time.time()

    min_q = IP_MINUTE_HISTORY[client_ip]
    cutoff_min = now - MINUTE_WINDOW
    while min_q and min_q[0] < cutoff_min:
        min_q.popleft()

    day_q = IP_DAILY_HISTORY[client_ip]
    cutoff_day = now - DAILY_WINDOW
    while day_q and day_q[0] < cutoff_day:
        day_q.popleft()

    if len(min_q) >= MAX_PER_MINUTE:
        return jsonify({
            "success": False,
            "message": "Too many requests. Please wait 1 minute before retrying."
        }), 429

    if len(day_q) >= MAX_PER_DAY:
        return jsonify({
            "success": False,
            "message": "Daily limit reached (Max 100 requests/day per IP). Please try again tomorrow."
        }), 429

    min_q.append(now)
    day_q.append(now)


@app.after_request
def apply_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


def validate_inputs(transfer_code: str, confirmation_code: str) -> bool:
    if not transfer_code or not confirmation_code:
        return False
    if len(transfer_code) > 64 or len(confirmation_code) > 16:
        return False
    return True


OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Battle Cats Save File Editor API",
        "version": "1.0.3",
        "description": "High-Performance Battle Cats Save Customization and Transfer API Engine."
    },
    "paths": {
        "/info": {
            "post": {
                "tags": ["Save Management"],
                "summary": "Inspect Save File Information",
                "description": "Download save file metadata from PONOS servers using a valid Transfer Code, Confirmation PIN, and Country Code.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/InfoRequest"},
                            "example": {
                                "transfer_code": "1a2b3c4d5",
                                "confirmation_code": "1234",
                                "country_code": "kr"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Save file information retrieved successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/InfoResponse"},
                                "example": {
                                    "success": True,
                                    "message": "Save info retrieved successfully.",
                                    "game_version": 140300,
                                    "catfood": 6767,
                                    "xp": 50000,
                                    "rare_tickets": 10,
                                    "platinum_tickets": 2,
                                    "legend_tickets": 1
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid or expired transfer code / PIN",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/edit": {
            "post": {
                "tags": ["Save Management"],
                "summary": "Modify Save File & Re-Upload",
                "description": "Apply target modifications, sync server managed items, and issue new transfer credentials.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/EditRequest"},
                            "example": {
                                "transfer_code": "1a2b3c4d5",
                                "confirmation_code": "1234",
                                "country_code": "kr",
                                "catfood": 45000,
                                "xp": 99999999,
                                "rare_tickets": 999,
                                "platinum_tickets": 99,
                                "legend_tickets": 9,
                                "unlock_cats": True,
                                "max_treasures": True,
                                "enable_safety": False
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Save file modified and re-uploaded successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/EditResponse"},
                                "example": {
                                    "success": True,
                                    "message": "Save modified and uploaded successfully.",
                                    "new_transfer_code": "9z8y7x6w5",
                                    "new_confirmation_code": "5678"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid input or expired codes",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        }
                    },
                    "502": {
                        "description": "Failed to re-upload to PONOS servers",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        }
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "InfoRequest": {
                "type": "object",
                "required": ["transfer_code", "confirmation_code", "country_code"],
                "properties": {
                    "transfer_code": {"type": "string", "description": "PONOS 9-digit Transfer Code"},
                    "confirmation_code": {"type": "string", "description": "PONOS 4-digit PIN Code"},
                    "country_code": {"type": "string", "description": "Region Code (kr, jp, en, tw)"}
                }
            },
            "EditRequest": {
                "type": "object",
                "required": ["transfer_code", "confirmation_code", "country_code"],
                "properties": {
                    "transfer_code": {"type": "string", "description": "PONOS 9-digit Transfer Code"},
                    "confirmation_code": {"type": "string", "description": "PONOS 4-digit PIN Code"},
                    "country_code": {"type": "string", "description": "Region Code (kr, jp, en, tw)"},
                    "catfood": {"type": "integer", "description": "Target Cat Food balance"},
                    "xp": {"type": "integer", "description": "Target XP balance"},
                    "normal_tickets": {"type": "integer", "description": "Target Normal Tickets count"},
                    "rare_tickets": {"type": "integer", "description": "Target Rare Tickets count"},
                    "platinum_tickets": {"type": "integer", "description": "Target Platinum Tickets count"},
                    "legend_tickets": {"type": "integer", "description": "Target Legend Tickets count"},
                    "platinum_shards": {"type": "integer", "description": "Target Platinum Shards count"},
                    "np": {"type": "integer", "description": "Target NP (Cat Point) balance"},
                    "leadership": {"type": "integer", "description": "Target Leadership count"},
                    "unlock_cats": {"type": "boolean", "default": False, "description": "Unlock all obtainable characters"},
                    "unlock_cat_ids": {"type": "array", "items": {"type": "integer"}, "description": "List of specific Cat IDs to unlock (e.g. [0, 1, 555])"},
                    "remove_cat_ids": {"type": "array", "items": {"type": "integer"}, "description": "List of specific Cat IDs to remove/lock"},
                    "clear_all_stages": {"type": "boolean", "default": False, "description": "Clear all story chapters & Aku Realm"},
                    "clear_chapters": {"type": "array", "items": {"type": "integer"}, "description": "List of Chapter IDs to clear (0=Eo1, 1=Eo2, 2=Eo3, 3=It1, 4=It2, 5=It3, 6=Co1, 7=Co2, 8=Co3, 9=Aku)"},
                    "clear_stages": {"type": "array", "items": {"type": "object", "properties": {"chapter": {"type": "integer"}, "stage": {"type": "integer"}}}, "description": "List of specific stages to clear"},
                    "max_treasures": {"type": "boolean", "default": False, "description": "Set all story chapter treasures to Gold (Superior)"},
                    "max_chapter_treasures": {"type": "array", "items": {"type": "integer"}, "description": "List of Chapter IDs to set all treasures to Gold"},
                    "stage_treasures": {"type": "array", "items": {"type": "object", "properties": {"chapter": {"type": "integer"}, "stage": {"type": "integer"}, "treasure": {"type": "integer", "description": "1=Inferior (조잡), 2=Normal (보통), 3=Superior/Gold (최고)"}}}, "description": "List of specific stage treasure quality settings"},
                    "enable_safety": {"type": "boolean", "default": False, "description": "Enable ban safety limit clamping"}
                }
            },
            "InfoResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
                    "game_version": {"type": "integer", "description": "Game version number"},
                    "catfood": {"type": "integer", "description": "Current Cat Food balance"},
                    "xp": {"type": "integer", "description": "Current XP balance"},
                    "normal_tickets": {"type": "integer", "description": "Current Normal Tickets count"},
                    "rare_tickets": {"type": "integer", "description": "Current Rare Tickets count"},
                    "platinum_tickets": {"type": "integer", "description": "Current Platinum Tickets count"},
                    "legend_tickets": {"type": "integer", "description": "Current Legend Tickets count"},
                    "platinum_shards": {"type": "integer", "description": "Current Platinum Shards count"},
                    "np": {"type": "integer", "description": "Current NP balance"},
                    "leadership": {"type": "integer", "description": "Current Leadership count"}
                }
            },
            "EditResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
                    "transfer_code": {"type": "string", "description": "PONOS Transfer Code"},
                    "confirmation_code": {"type": "string", "description": "PONOS Confirmation PIN"}
                }
            },
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": False},
                    "message": {"type": "string", "description": "Error description"}
                }
            }
        }
    }
}

SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Battle Cats Save File Editor API Documentation</title>
<meta name="description" content="Official REST API Documentation for Battle Cats Save Customization, Binary Patching, and PONOS Cloud Sync Engine.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root[data-theme="light"] {
    --bg: #f8fafc;
    --surface: #ffffff;
    --border: #e2e8f0;
    --text: #0f172a;
    --muted: #64748b;
    --primary: #0284c7;
    --btn-bg: #f1f5f9;
    --code-bg: #0f172a;
    --code-text: #f8fafc;
    --badge-get: #0284c7;
    --badge-post: #16a34a;
    --table-header: #f1f5f9;
  }

  :root[data-theme="dark"] {
    --bg: #090d16;
    --surface: #111827;
    --border: #1f2937;
    --text: #f9fafb;
    --muted: #9ca3af;
    --primary: #38bdf8;
    --btn-bg: #1f2937;
    --code-bg: #030712;
    --code-text: #f9fafb;
    --badge-get: #38bdf8;
    --badge-post: #4ade80;
    --table-header: #1f2937;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', sans-serif; background-color: var(--bg); color: var(--text); line-height: 1.6; }
  header { background-color: var(--surface); border-bottom: 1px solid var(--border); padding: 1.25rem 2rem; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }
  .logo { font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 1.25rem; color: var(--text); text-decoration: none; display: flex; align-items: center; gap: 0.5rem; }
  .logo span { color: var(--primary); }
  .nav-actions { display: flex; gap: 1rem; align-items: center; }
  .theme-btn { background: var(--btn-bg); border: 1px solid var(--border); color: var(--text); padding: 0.5rem 1rem; border-radius: 0.5rem; cursor: pointer; font-weight: 500; font-size: 0.875rem; transition: all 0.2s; }
  .theme-btn:hover { border-color: var(--primary); color: var(--primary); }

  .container { max-width: 1200px; margin: 0 auto; padding: 2.5rem 1.5rem; }
  .hero { background-color: var(--surface); border: 1px solid var(--border); border-radius: 1rem; padding: 2.5rem; margin-bottom: 2rem; }
  .hero h1 { font-family: 'Plus Jakarta Sans', sans-serif; font-size: 2.25rem; font-weight: 800; margin-bottom: 0.75rem; line-height: 1.2; }
  .hero p { color: var(--muted); font-size: 1.125rem; max-width: 800px; margin-bottom: 1.5rem; }
  .badge-list { display: flex; gap: 0.75rem; flex-wrap: wrap; }
  .chip { background-color: var(--btn-bg); border: 1px solid var(--border); font-size: 0.8125rem; font-weight: 600; padding: 0.25rem 0.75rem; border-radius: 9999px; }

  .section-title { font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.5rem; font-weight: 700; margin: 2rem 0 1rem; }
  
  .card { background-color: var(--surface); border: 1px solid var(--border); border-radius: 0.75rem; margin-bottom: 1.5rem; overflow: hidden; }
  .card-header { padding: 1.25rem 1.5rem; display: flex; align-items: center; gap: 1rem; border-bottom: 1px solid var(--border); }
  .method { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.875rem; padding: 0.25rem 0.625rem; border-radius: 0.375rem; color: #fff; text-transform: uppercase; }
  .method.get { background-color: var(--badge-get); }
  .method.post { background-color: var(--badge-post); }
  .endpoint-path { font-family: 'JetBrains Mono', monospace; font-size: 1.125rem; font-weight: 600; }
  .card-body { padding: 1.5rem; }
  .card-body p { color: var(--muted); margin-bottom: 1rem; }

  table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.875rem; }
  th, td { text-align: left; padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); }
  th { background-color: var(--table-header); font-weight: 600; }
  td code { font-family: 'JetBrains Mono', monospace; background: var(--btn-bg); padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.8125rem; }

  pre.code-block { background-color: var(--code-bg); color: var(--code-text); padding: 1.25rem; border-radius: 0.5rem; overflow-x: auto; font-family: 'JetBrains Mono', monospace; font-size: 0.875rem; margin-top: 1rem; }
</style>
</head>
<body>
<header>
  <a href="/" class="logo">Battle Cats <span>Save Editor API</span></a>
  <div class="nav-actions">
    <button class="theme-btn" onclick="toggleTheme()" id="theme-text">Dark Mode</button>
  </div>
</header>
<div class="container">
  <div class="hero">
    <h1>Battle Cats Save File Editor REST API</h1>
    <p>High-performance REST API for Battle Cats save customization, binary patching, and cloud PONOS transfer synchronization.</p>
    <div class="badge-list">
      <span class="chip">v1.0.3</span>
      <span class="chip">OpenAPI 3.0</span>
      <span class="chip">JSON REST API</span>
    </div>
  </div>

  <h2 class="section-title">Endpoints</h2>

  <div class="card">
    <div class="card-header">
      <span class="method get">GET</span>
      <span class="endpoint-path">/</span>
    </div>
    <div class="card-body">
      <p>Health check endpoint retrieving service status.</p>
      <pre class="code-block"><code>{"service": "Battle Cats Save File Editor API", "status": "online", "version": "1.0.3"}</code></pre>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <span class="method post">POST</span>
      <span class="endpoint-path">/info</span>
    </div>
    <div class="card-body">
      <p>Downloads save metadata from PONOS servers using a Transfer Code and PIN.</p>
      <pre class="code-block"><code>POST /info
Content-Type: application/json

{
  "transfer_code": "1a2b3c4d5",
  "confirmation_code": "1234",
  "country_code": "kr"
}</code></pre>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <span class="method post">POST</span>
      <span class="endpoint-path">/edit</span>
    </div>
    <div class="card-body">
      <p>Applies requested modifications to save data and re-uploads to PONOS server to obtain new transfer credentials.</p>
      <pre class="code-block"><code>POST /edit
Content-Type: application/json

{
  "transfer_code": "1a2b3c4d5",
  "confirmation_code": "1234",
  "country_code": "kr",
  "catfood": 45000,
  "xp": 99999999,
  "unlock_cats": true,
  "max_treasures": true
}</code></pre>
    </div>
  </div>

  <h2 class="section-title">Code Integration Examples (17 Languages)</h2>
  <div class="card">
    <div class="card-body">
      <p>Standalone executable code examples are available for 17 popular programming languages:</p>
      <div class="badge-list" style="margin-top: 1rem;">
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.py" target="_blank" class="chip">Python (example.py)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.js" target="_blank" class="chip">JavaScript (example.js)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.ts" target="_blank" class="chip">TypeScript (example.ts)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.go" target="_blank" class="chip">Go (example.go)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.rs" target="_blank" class="chip">Rust (example.rs)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.cpp" target="_blank" class="chip">C++ (example.cpp)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.cs" target="_blank" class="chip">C# (example.cs)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.c" target="_blank" class="chip">C (example.c)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.java" target="_blank" class="chip">Java (example.java)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.kt" target="_blank" class="chip">Kotlin (example.kt)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.swift" target="_blank" class="chip">Swift (example.swift)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.php" target="_blank" class="chip">PHP (example.php)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.rb" target="_blank" class="chip">Ruby (example.rb)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.dart" target="_blank" class="chip">Dart (example.dart)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.mojo" target="_blank" class="chip">Mojo (example.mojo)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.sh" target="_blank" class="chip">Shell (example.sh)</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.ps1" target="_blank" class="chip">PowerShell (example.ps1)</a>
      </div>
    </div>
  </div>
</div>
<script>
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  document.getElementById('theme-text').textContent = next === 'dark' ? 'Light Mode' : 'Dark Mode';
}
</script>
</body>
</html>"""


@app.route("/openapi.json", methods=["GET"])
def openapi_spec():
    return jsonify(OPENAPI_SPEC)


@app.route("/docs", methods=["GET"])
def docs():
    resp = app.make_response(SWAGGER_HTML)
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "service": "Battle Cats Save File Editor API",
        "version": "1.0.3"
    })


@app.route("/info", methods=["POST"])
def inspect_save():
    data = request.get_json(silent=True) or {}
    tc = str(data.get("transfer_code") or data.get("tc") or "").strip()
    cc = str(data.get("confirmation_code") or data.get("cc") or data.get("confirmation_pin") or "").strip()
    country = str(data.get("country_code") or data.get("country") or data.get("cc_str") or "").strip()

    if not validate_inputs(tc, cc) or not country:
        return jsonify({"success": False, "message": "transfer_code, confirmation_code, and country_code are required."}), 400

    sf, sh = download_ponos_save(tc, cc, country)
    if sf is None:
        return jsonify({"success": False, "message": "Invalid or expired transfer code / PIN."}), 400

    gv = getattr(getattr(sf, "game_version", None), "game_version", 140300)

    return jsonify({
        "success": True,
        "message": "Save info retrieved successfully.",
        "game_version": gv,
        "catfood": getattr(sf, "catfood", 0),
        "xp": getattr(sf, "xp", 0),
        "normal_tickets": getattr(sf, "normal_tickets", 0),
        "rare_tickets": getattr(sf, "rare_tickets", 0),
        "platinum_tickets": getattr(sf, "platinum_tickets", 0),
        "legend_tickets": getattr(sf, "legend_tickets", 0),
        "platinum_shards": getattr(sf, "platinum_shards", 0),
        "np": getattr(sf, "np", 0),
        "leadership": getattr(sf, "leadership", 0),
    })


@app.route("/edit", methods=["POST"])
def edit_save():
    data = request.get_json(silent=True) or {}
    tc = str(data.get("transfer_code") or data.get("tc") or "").strip()
    cc = str(data.get("confirmation_code") or data.get("cc") or data.get("confirmation_pin") or "").strip()
    country = str(data.get("country_code") or data.get("country") or data.get("cc_str") or "").strip()

    catfood = data.get("catfood")
    xp = data.get("xp")
    normal_tickets = data.get("normal_tickets")
    rare_tickets = data.get("rare_tickets")
    platinum_tickets = data.get("platinum_tickets")
    legend_tickets = data.get("legend_tickets")
    platinum_shards = data.get("platinum_shards")
    np = data.get("np")
    leadership = data.get("leadership")

    unlock_cats = bool(data.get("unlock_cats", False))
    unlock_cat_ids = data.get("unlock_cat_ids")
    remove_cat_ids = data.get("remove_cat_ids")

    clear_all_stages = bool(data.get("clear_all_stages", False))
    clear_chapters = data.get("clear_chapters")
    clear_stages = data.get("clear_stages")

    max_treasures = bool(data.get("max_treasures", False))
    max_chapter_treasures = data.get("max_chapter_treasures")
    stage_treasures = data.get("stage_treasures")

    enable_safety = bool(data.get("enable_safety", False))

    if not validate_inputs(tc, cc) or not country:
        return jsonify({"success": False, "message": "transfer_code, confirmation_code, and country_code are required."}), 400

    has_any_edit = any([
        catfood is not None, xp is not None, normal_tickets is not None,
        rare_tickets is not None, platinum_tickets is not None, legend_tickets is not None,
        platinum_shards is not None, np is not None, leadership is not None,
        unlock_cats, unlock_cat_ids, remove_cat_ids,
        clear_all_stages, clear_chapters, clear_stages,
        max_treasures, max_chapter_treasures, stage_treasures
    ])

    if not has_any_edit:
        return jsonify({"success": False, "message": "At least one modification value or flag must be specified."}), 400

    sf, sh = download_ponos_save(tc, cc, country)
    if sf is None:
        return jsonify({"success": False, "message": "Invalid or expired transfer code / PIN."}), 400

    res, codes = patch_and_upload_save(
        save_file=sf,
        server_handler=sh,
        cc_str=country,
        catfood=catfood,
        xp=xp,
        normal_tickets=normal_tickets,
        rare_tickets=rare_tickets,
        platinum_tickets=platinum_tickets,
        legend_tickets=legend_tickets,
        platinum_shards=platinum_shards,
        np=np,
        leadership=leadership,
        unlock_cats=unlock_cats,
        unlock_cat_ids=unlock_cat_ids,
        remove_cat_ids=remove_cat_ids,
        clear_all_stages=clear_all_stages,
        clear_chapters=clear_chapters,
        clear_stages=clear_stages,
        max_treasures=max_treasures,
        max_chapter_treasures=max_chapter_treasures,
        stage_treasures=stage_treasures,
        enable_safety=enable_safety,
    )

    if codes is None:
        return jsonify({"success": False, "message": "Failed to re-upload modified save to PONOS servers."}), 502

    new_t, new_c = codes
    return jsonify({
        "success": True,
        "message": "Save modified and uploaded successfully.",
        "transfer_code": new_t,
        "confirmation_code": new_c,
        "new_transfer_code": new_t,
        "new_confirmation_code": new_c,
        "details": res,
    })
