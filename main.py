from flask import Flask, request, jsonify
import time
import traceback
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
_LAST_CLEANUP = 0

MINUTE_WINDOW = 60
DAILY_WINDOW = 86400
CLEANUP_INTERVAL = 3600

MAX_PER_MINUTE = 10
MAX_PER_DAY = 100
REQUEST_TIMEOUT = 55


def get_client_ip() -> str:
    xf = request.headers.get("X-Forwarded-For")
    if xf:
        return xf.split(",")[0].strip()
    xr = request.headers.get("X-Real-IP")
    if xr:
        return xr.strip()
    return request.remote_addr or "127.0.0.1"


BANNED_IPS = {"211.201.59.121"}


def _cleanup_stale_ips():
    global _LAST_CLEANUP
    now = time.time()
    if now - _LAST_CLEANUP < CLEANUP_INTERVAL:
        return
    _LAST_CLEANUP = now
    stale_ips = []
    for ip, dq in list(IP_DAILY_HISTORY.items()):
        if not dq or dq[-1] < now - DAILY_WINDOW:
            stale_ips.append(ip)
    for ip in stale_ips:
        IP_MINUTE_HISTORY.pop(ip, None)
        IP_DAILY_HISTORY.pop(ip, None)


def safe_int(val, default=None, lo=0, hi=INT32_MAX):
    if val is None:
        return default
    try:
        v = int(val)
        return max(lo, min(v, hi))
    except (ValueError, TypeError):
        return default


@app.before_request
def handle_rate_limits():
    if request.method == "OPTIONS":
        return

    client_ip = get_client_ip()

    if client_ip in BANNED_IPS:
        return jsonify({
            "success": False,
            "message": "Access denied."
        }), 403

    now = time.time()
    request._start_time = now

    _cleanup_stale_ips()

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
    if not all(c.isalnum() for c in transfer_code):
        return False
    if not all(c.isalnum() for c in confirmation_code):
        return False
    return True


def _check_timeout():
    start = getattr(request, '_start_time', None)
    if start and (time.time() - start) > REQUEST_TIMEOUT:
        return True
    return False


OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Battle Cats Save File Editor API",
        "version": "1.0.5",
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
                    "catseyes": {"description": "Target Catseye count for all types or list per type [EX, Rare, S.Rare, U.Rare, Legend]"},
                    "catfruit": {"description": "Target Catfruit / Matatabi count"},
                    "catamins": {"description": "Target Catamins A/B/C count"},
                    "gamatoto_level": {"type": "integer", "description": "Target Gamatoto level (e.g. 150)"},
                    "gamatoto_xp": {"type": "integer", "description": "Target Gamatoto XP value"},
                    "gamatoto_helpers": {"type": "boolean", "description": "Set all 10 Gamatoto helpers to Legend/Grandmaster rarity"},
                    "ototo_engineers": {"type": "integer", "description": "Target Ototo engineer count (max 10)"},
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
  .hero .sub-desc { color: var(--muted); font-size: 0.9375rem; line-height: 1.7; max-width: 900px; margin-bottom: 1.5rem; }
  .badge-list { display: flex; gap: 0.75rem; flex-wrap: wrap; }
  .chip { background-color: var(--btn-bg); border: 1px solid var(--border); font-size: 0.8125rem; font-weight: 600; padding: 0.25rem 0.75rem; border-radius: 9999px; color: var(--text); text-decoration: none; transition: all 0.2s; }
  .chip:hover { border-color: var(--primary); color: var(--primary); }

  .section-title { font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.5rem; font-weight: 700; margin: 2.5rem 0 1rem; }
  .sub-section-title { font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.125rem; font-weight: 700; margin: 1.75rem 0 0.75rem; color: var(--text); }
  
  .card { background-color: var(--surface); border: 1px solid var(--border); border-radius: 0.75rem; margin-bottom: 1.5rem; overflow: hidden; }
  .card-header { padding: 1.25rem 1.5rem; display: flex; align-items: center; gap: 1rem; border-bottom: 1px solid var(--border); }
  .method { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.875rem; padding: 0.25rem 0.625rem; border-radius: 0.375rem; color: #fff; text-transform: uppercase; }
  .method.get { background-color: var(--badge-get); }
  .method.post { background-color: var(--badge-post); }
  .endpoint-path { font-family: 'JetBrains Mono', monospace; font-size: 1.125rem; font-weight: 600; }
  .endpoint-desc { font-size: 0.875rem; color: var(--muted); margin-left: auto; }
  .card-body { padding: 1.5rem; }
  .card-body p { color: var(--muted); margin-bottom: 1rem; line-height: 1.7; }
  .card-body .detail-note { background: var(--btn-bg); border-left: 3px solid var(--primary); padding: 0.75rem 1rem; border-radius: 0 0.375rem 0.375rem 0; margin: 1rem 0; font-size: 0.8125rem; color: var(--muted); line-height: 1.6; }
  .card-body .warn-note { background: var(--btn-bg); border-left: 3px solid #f59e0b; padding: 0.75rem 1rem; border-radius: 0 0.375rem 0.375rem 0; margin: 1rem 0; font-size: 0.8125rem; color: var(--muted); line-height: 1.6; }
  .card-body .warn-note strong, .card-body .detail-note strong { color: var(--text); }

  table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.875rem; }
  th, td { text-align: left; padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); }
  th { background-color: var(--table-header); font-weight: 600; }
  td code { font-family: 'JetBrains Mono', monospace; background: var(--btn-bg); padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.8125rem; }

  pre.code-block { background-color: var(--code-bg); color: var(--code-text); padding: 1.25rem; border-radius: 0.5rem; overflow-x: auto; font-family: 'JetBrains Mono', monospace; font-size: 0.875rem; margin-top: 1rem; }

  .status-badge { display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; font-weight: 700; padding: 0.125rem 0.5rem; border-radius: 0.25rem; color: #fff; }
  .status-200 { background: #16a34a; }
  .status-400 { background: #f59e0b; }
  .status-500 { background: #ef4444; }
  .status-502 { background: #ef4444; }
  .status-504 { background: #ef4444; }
  .status-404 { background: #6b7280; }
  .status-405 { background: #6b7280; }
  .status-413 { background: #6b7280; }

  .flow-steps { display: flex; flex-direction: column; gap: 0; margin: 1.5rem 0; }
  .flow-step { display: flex; align-items: flex-start; gap: 1rem; position: relative; padding-bottom: 1.5rem; }
  .flow-step:last-child { padding-bottom: 0; }
  .flow-step::before { content: ''; position: absolute; left: 1.0625rem; top: 2.25rem; bottom: 0; width: 2px; background: var(--border); }
  .flow-step:last-child::before { display: none; }
  .step-num { flex-shrink: 0; width: 2.125rem; height: 2.125rem; background: var(--primary); color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.875rem; font-family: 'JetBrains Mono', monospace; }
  .step-content { flex: 1; }
  .step-content strong { display: block; font-size: 0.9375rem; margin-bottom: 0.25rem; }
  .step-content span { color: var(--muted); font-size: 0.8125rem; line-height: 1.6; }

  .param-group-title { font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; font-size: 0.9375rem; color: var(--primary); margin: 1.5rem 0 0.5rem; padding-bottom: 0.25rem; border-bottom: 2px solid var(--primary); display: inline-block; }
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
    <p>High-performance REST API for Battle Cats save customization and transfer credential management.</p>
    <div class="sub-desc">
      Automated API interface for inspecting save data and applying requested account modifications, returning updated transfer credentials in a single request.
    </div>
    <div class="badge-list">
      <span class="chip">v1.0.5</span>
      <span class="chip">OpenAPI 3.0</span>
      <span class="chip">JSON REST API</span>
      <span class="chip">Content-Type: application/json</span>
      <span class="chip">No API Key Required</span>
    </div>
  </div>

  <h2 class="section-title">Usage Overview</h2>
  <div class="card">
    <div class="card-body">
      <p>Each API operation processes the request and returns fresh transfer credentials for in-game use.</p>
      <div class="flow-steps">
        <div class="flow-step">
          <div class="step-num">1</div>
          <div class="step-content">
            <strong>Authenticate Request</strong>
            <span>Provide the current Transfer Code, Confirmation PIN, and game region code.</span>
          </div>
        </div>
        <div class="flow-step">
          <div class="step-num">2</div>
          <div class="step-content">
            <strong>Process Modifications</strong>
            <span>Requested resource, cat, and stage modifications are applied according to parameters.</span>
          </div>
        </div>
        <div class="flow-step">
          <div class="step-num">3</div>
          <div class="step-content">
            <strong>Receive Credentials</strong>
            <span>A new Transfer Code and Confirmation PIN are generated and returned for in-game data import.</span>
          </div>
        </div>
      </div>
      <div class="warn-note">
        <strong>Notice:</strong> Each Transfer Code + PIN pair is single-use. Always use the new credentials returned in the response for in-game transfer.
      </div>
    </div>
  </div>

  <h2 class="section-title">Endpoints</h2>

  <div class="card">
    <div class="card-header">
      <span class="method get">GET</span>
      <span class="endpoint-path">/</span>
      <span class="endpoint-desc">Health Check</span>
    </div>
    <div class="card-body">
      <p>Returns the current service status and API version. Use this endpoint to verify the server is online before making edit requests.</p>
      <h4 class="sub-section-title">Response</h4>
      <pre class="code-block"><code>{
  "service": "Battle Cats Save File Editor API",
  "status": "online",
  "version": "1.0.5"
}</code></pre>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <span class="method post">POST</span>
      <span class="endpoint-path">/info</span>
      <span class="endpoint-desc">Inspect Save Data</span>
    </div>
    <div class="card-body">
      <p>Downloads and inspects save metadata from PONOS servers. Returns the player's current resource balances and game version without modifying anything.</p>

      <h4 class="sub-section-title">Request Body</h4>
      <table>
        <thead>
          <tr><th>Field</th><th>Type</th><th>Required</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr><td><code>transfer_code</code></td><td>string</td><td>Yes</td><td>PONOS Transfer Code obtained from in-game Data Transfer menu</td></tr>
          <tr><td><code>confirmation_code</code></td><td>string</td><td>Yes</td><td>4-digit Confirmation PIN paired with the Transfer Code</td></tr>
          <tr><td><code>country_code</code></td><td>string</td><td>Yes</td><td>Game region code: <code>"kr"</code>, <code>"jp"</code>, <code>"en"</code>, or <code>"tw"</code></td></tr>
        </tbody>
      </table>
      <div class="detail-note">
        <strong>Aliases:</strong> <code>transfer_code</code> also accepts <code>tc</code>. <code>confirmation_code</code> also accepts <code>cc</code> or <code>confirmation_pin</code>. <code>country_code</code> also accepts <code>country</code> or <code>cc_str</code>.
      </div>

      <h4 class="sub-section-title">Example Request</h4>
      <pre class="code-block"><code>POST /info
Content-Type: application/json

{
  "transfer_code": "1a2b3c4d5",
  "confirmation_code": "1234",
  "country_code": "kr"
}</code></pre>

      <h4 class="sub-section-title">Success Response <span class="status-badge status-200">200</span></h4>
      <pre class="code-block"><code>{
  "success": true,
  "message": "Save info retrieved successfully.",
  "game_version": 140300,
  "catfood": 1250,
  "xp": 5000000,
  "normal_tickets": 12,
  "rare_tickets": 3,
  "platinum_tickets": 0,
  "legend_tickets": 0,
  "platinum_shards": 5,
  "np": 230,
  "leadership": 0
}</code></pre>

      <h4 class="sub-section-title">Response Fields</h4>
      <table>
        <thead>
          <tr><th>Field</th><th>Type</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr><td><code>success</code></td><td>boolean</td><td>Whether the operation completed successfully</td></tr>
          <tr><td><code>message</code></td><td>string</td><td>Human-readable status message</td></tr>
          <tr><td><code>game_version</code></td><td>integer</td><td>Internal game version number, e.g. <code>140300</code> represents v14.3.0</td></tr>
          <tr><td><code>catfood</code></td><td>integer</td><td>Current Cat Food balance</td></tr>
          <tr><td><code>xp</code></td><td>integer</td><td>Current XP balance</td></tr>
          <tr><td><code>normal_tickets</code></td><td>integer</td><td>Current Normal Cat Ticket count</td></tr>
          <tr><td><code>rare_tickets</code></td><td>integer</td><td>Current Rare Ticket count</td></tr>
          <tr><td><code>platinum_tickets</code></td><td>integer</td><td>Current Platinum Ticket count</td></tr>
          <tr><td><code>legend_tickets</code></td><td>integer</td><td>Current Legend Ticket count</td></tr>
          <tr><td><code>platinum_shards</code></td><td>integer</td><td>Current Platinum Shard count</td></tr>
          <tr><td><code>np</code></td><td>integer</td><td>Current NP balance</td></tr>
          <tr><td><code>leadership</code></td><td>integer</td><td>Current Leadership count</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <span class="method post">POST</span>
      <span class="endpoint-path">/edit</span>
      <span class="endpoint-desc">Modify Save Data</span>
    </div>
    <div class="card-body">
      <p>Downloads the save from PONOS servers, applies all requested binary modifications, re-uploads the patched save, and returns new transfer credentials. You can combine any number of editable parameters in a single request &mdash; they are all applied atomically before the upload.</p>
      <div class="detail-note">
        <strong>All parameters are optional</strong> except the three authentication fields. Include only the fields you want to modify. Omitted fields remain unchanged in the save data.
      </div>

      <h4 class="sub-section-title">Authentication Fields</h4>
      <table>
        <thead>
          <tr><th>Field</th><th>Type</th><th>Required</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr><td><code>transfer_code</code></td><td>string</td><td>Yes</td><td>PONOS Transfer Code</td></tr>
          <tr><td><code>confirmation_code</code></td><td>string</td><td>Yes</td><td>4-digit Confirmation PIN</td></tr>
          <tr><td><code>country_code</code></td><td>string</td><td>Yes</td><td>Region: <code>"kr"</code>, <code>"jp"</code>, <code>"en"</code>, or <code>"tw"</code></td></tr>
        </tbody>
      </table>

      <div class="param-group-title">Currency &amp; Resources</div>
      <table>
        <thead>
          <tr><th>Parameter</th><th>Type</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr><td><code>catfood</code></td><td>integer</td><td>Set Cat Food to this exact value. With safety mode: clamped to 45,000 max</td></tr>
          <tr><td><code>xp</code></td><td>integer</td><td>Set XP to this exact value. With safety mode: clamped to 99,999,999 max</td></tr>
          <tr><td><code>np</code></td><td>integer</td><td>Set NP to this exact value</td></tr>
          <tr><td><code>leadership</code></td><td>integer</td><td>Set Leadership count. Max: 32,767</td></tr>
        </tbody>
      </table>

      <div class="param-group-title">Tickets</div>
      <table>
        <thead>
          <tr><th>Parameter</th><th>Type</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr><td><code>normal_tickets</code></td><td>integer</td><td>Set Normal Cat Ticket count</td></tr>
          <tr><td><code>rare_tickets</code></td><td>integer</td><td>Set Rare Ticket count</td></tr>
          <tr><td><code>platinum_tickets</code></td><td>integer</td><td>Set Platinum Ticket count</td></tr>
          <tr><td><code>legend_tickets</code></td><td>integer</td><td>Set Legend Ticket count</td></tr>
          <tr><td><code>platinum_shards</code></td><td>integer</td><td>Set Platinum Shard count</td></tr>
        </tbody>
      </table>

      <div class="param-group-title">Materials &amp; Items</div>
      <table>
        <thead>
          <tr><th>Parameter</th><th>Type</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><code>catseyes</code></td>
            <td>integer | array | object</td>
            <td>
              <strong>integer</strong>: Sets all 6 catseye types to this value<br>
              <strong>array</strong>: <code>[EX, Rare, Super Rare, Uber Rare, Legend, Dark]</code> in order<br>
              <strong>object</strong>: <code>{"ex": 999, "rare": 999, "super_rare": 999, "uber_rare": 999, "legend": 999, "dark": 999}</code>
            </td>
          </tr>
          <tr>
            <td><code>catfruit</code></td>
            <td>integer | array</td>
            <td>
              <strong>integer</strong>: Sets all catfruit and seed types to this value<br>
              <strong>array</strong>: Individual catfruit counts by slot index
            </td>
          </tr>
          <tr>
            <td><code>behemoth_stones</code></td>
            <td>integer | array</td>
            <td>
              <strong>integer</strong>: Sets all behemoth stone and gem types to this value<br>
              <strong>array</strong>: Individual stone counts by slot index. Alias: <code>stones</code>
            </td>
          </tr>
          <tr>
            <td><code>catamins</code></td>
            <td>integer | object</td>
            <td>
              <strong>integer</strong>: Sets Catamins A, B, and C all to this value<br>
              <strong>object</strong>: <code>{"a": 999, "b": 999, "c": 999}</code><br>
              Individual keys <code>catamins_a</code>, <code>catamins_b</code>, <code>catamins_c</code> also accepted
            </td>
          </tr>
          <tr>
            <td><code>battle_items</code></td>
            <td>integer | array</td>
            <td>Set battle item counts. Integer sets all items uniformly</td>
          </tr>
          <tr>
            <td><code>base_materials</code></td>
            <td>integer | array | object</td>
            <td>
              <strong>integer</strong>: Sets all Ototo base material types to this value<br>
              <strong>object</strong>: <code>{"bricks": 9999, "feathers": 9999, "coal": 9999, ...}</code>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="param-group-title">Gamatoto &amp; Ototo</div>
      <table>
        <thead>
          <tr><th>Parameter</th><th>Type</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr><td><code>gamatoto_level</code></td><td>integer</td><td>Set Gamatoto expedition level</td></tr>
          <tr><td><code>gamatoto_xp</code></td><td>integer</td><td>Set Gamatoto XP value</td></tr>
          <tr>
            <td><code>gamatoto_helpers</code></td>
            <td>array | string | boolean</td>
            <td>
              <strong>array</strong>: Exactly 10 rarity strings e.g. <code>["legend", "legend", "rare", ...]</code><br>
              <strong>string</strong>: Fill all 10 slots with one rarity: <code>"legend"</code>, <code>"rare"</code>, or <code>"common"</code><br>
              <strong>boolean</strong>: <code>true</code> fills all slots with Legend helpers
            </td>
          </tr>
          <tr><td><code>ototo_engineers</code></td><td>integer</td><td>Set Ototo engineer count. Max: 10</td></tr>
        </tbody>
      </table>

      <div class="param-group-title">Cats &amp; Characters</div>
      <table>
        <thead>
          <tr><th>Parameter</th><th>Type</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr><td><code>unlock_cats</code></td><td>boolean</td><td>Set to <code>true</code> to unlock all obtainable cats</td></tr>
          <tr><td><code>unlock_cat_ids</code></td><td>array[int]</td><td>Unlock specific cats by ID, e.g. <code>[0, 1, 555]</code></td></tr>
          <tr><td><code>remove_cat_ids</code></td><td>array[int]</td><td>Lock/remove specific cats by ID</td></tr>
          <tr>
            <td><code>cat_levels</code></td>
            <td>array[object]</td>
            <td>Set specific cat levels. Each object: <code>{"id": 0, "level": 50, "plus_level": 90}</code>. <code>plus_level</code> is optional</td>
          </tr>
          <tr>
            <td><code>cat_evolutions</code></td>
            <td>array[object]</td>
            <td>Set cat evolution forms. Each object: <code>{"id": 555, "form": 4}</code>. Form values: 1=Normal, 2=Evolved, 3=True Form, 4=Ultra Form. Automatically clamped to each cat's actual max form</td>
          </tr>
          <tr><td><code>max_cat_levels</code></td><td>boolean</td><td>Set all unlocked cats to max base level + max plus level</td></tr>
          <tr><td><code>true_form_all</code></td><td>boolean</td><td>Evolve all unlocked cats to their highest available form. Respects each cat's actual max form count. Alias: <code>max_cat_evolutions</code></td></tr>
        </tbody>
      </table>
      <div class="detail-note">
        <strong>Form Clamping:</strong> The <code>cat_evolutions</code> and <code>true_form_all</code> parameters automatically detect each cat's maximum available form from game data. If a cat only has 2 forms, requesting form 3 or 4 will safely clamp it to form 2.
      </div>

      <div class="param-group-title">Stages &amp; Treasures</div>
      <table>
        <thead>
          <tr><th>Parameter</th><th>Type</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr><td><code>clear_all_stages</code></td><td>boolean</td><td>Clear all Story mode and Aku Realm chapters</td></tr>
          <tr>
            <td><code>clear_chapters</code></td>
            <td>array</td>
            <td>Clear specific chapters by ID. Accepts integers <code>[0, 1, 2]</code> or objects with clear count <code>[{"chapter": 0, "clear_amount": 10}]</code></td>
          </tr>
          <tr>
            <td><code>clear_stages</code></td>
            <td>array[object]</td>
            <td>Clear specific stages with precise control: <code>[{"chapter": 0, "stage": 47, "clear_amount": 10}]</code></td>
          </tr>
          <tr><td><code>max_treasures</code></td><td>boolean</td><td>Set all story chapter treasures to Gold / Superior quality</td></tr>
          <tr>
            <td><code>max_chapter_treasures</code></td>
            <td>array</td>
            <td>Gold treasures for specific chapters. Accepts integers <code>[0, 1]</code> or objects <code>[{"chapter": 0, "treasure": 3}]</code>. Treasure levels: 1=Inferior, 2=Normal, 3=Gold</td>
          </tr>
          <tr>
            <td><code>stage_treasures</code></td>
            <td>array[object]</td>
            <td>Set individual stage treasure quality: <code>[{"chapter": 0, "stage": 0, "treasure": 3}]</code></td>
          </tr>
        </tbody>
      </table>

      <div class="param-group-title">Safety &amp; Protection</div>
      <table>
        <thead>
          <tr><th>Parameter</th><th>Type</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><code>enable_safety</code></td>
            <td>boolean</td>
            <td>Enable ban-safety value clamping. When <code>true</code>, Cat Food is clamped to &le; 45,000 and XP is clamped to &le; 99,999,999 to reduce detection risk</td>
          </tr>
        </tbody>
      </table>
      <div class="warn-note">
        <strong>Recommendation:</strong> Always set <code>enable_safety: true</code> for production use. Exceeding known safe limits may trigger PONOS server-side detection and result in account restrictions.
      </div>

      <h4 class="sub-section-title">Full Example Request</h4>
      <pre class="code-block"><code>POST /edit
Content-Type: application/json

{
  "transfer_code": "1a2b3c4d5",
  "confirmation_code": "1234",
  "country_code": "kr",
  "catfood": 45000,
  "xp": 99999999,
  "np": 9999,
  "normal_tickets": 999,
  "rare_tickets": 299,
  "platinum_tickets": 99,
  "legend_tickets": 9,
  "platinum_shards": 99,
  "catseyes": 999,
  "catfruit": 999,
  "behemoth_stones": 999,
  "catamins": 999,
  "gamatoto_level": 150,
  "gamatoto_xp": 9999999,
  "gamatoto_helpers": "legend",
  "ototo_engineers": 10,
  "base_materials": 9999,
  "unlock_cats": true,
  "max_cat_levels": true,
  "true_form_all": true,
  "clear_all_stages": true,
  "max_treasures": true,
  "enable_safety": true
}</code></pre>

      <h4 class="sub-section-title">Success Response <span class="status-badge status-200">200</span></h4>
      <pre class="code-block"><code>{
  "success": true,
  "message": "Save modified and uploaded successfully.",
  "transfer_code": "9x8y7z6w5",
  "confirmation_code": "5678",
  "new_transfer_code": "9x8y7z6w5",
  "new_confirmation_code": "5678",
  "details": {
    "catfood_set": 45000,
    "xp_set": 99999999,
    "unlocked_cats_count": 742,
    "updated_cat_evolutions_count": 742,
    "stages_cleared": true,
    "treasures_maxed": true
  }
}</code></pre>
      <div class="detail-note">
        <strong>Response Notes:</strong> <code>transfer_code</code> and <code>new_transfer_code</code> contain the same value for compatibility. The <code>details</code> object summarizes which modifications were successfully applied, including counts of affected cats, stages, and items.
      </div>
    </div>
  </div>

  <h2 class="section-title">HTTP Status Codes &amp; Error Handling</h2>
  <div class="card">
    <div class="card-body">
      <p>All error responses follow a consistent JSON structure with <code>success: false</code> and a descriptive <code>message</code> field.</p>
      <table>
        <thead>
          <tr><th>Status</th><th>Meaning</th><th>When It Occurs</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><span class="status-badge status-200">200</span></td>
            <td>Success</td>
            <td>Request completed successfully. Response contains requested data or new credentials</td>
          </tr>
          <tr>
            <td><span class="status-badge status-400">400</span></td>
            <td>Bad Request</td>
            <td>Missing required fields, invalid Transfer Code/PIN format, expired credentials, or no edit parameters specified</td>
          </tr>
          <tr>
            <td><span class="status-badge status-404">404</span></td>
            <td>Not Found</td>
            <td>Requested endpoint does not exist</td>
          </tr>
          <tr>
            <td><span class="status-badge status-405">405</span></td>
            <td>Method Not Allowed</td>
            <td>Wrong HTTP method used, e.g. GET on a POST-only endpoint</td>
          </tr>
          <tr>
            <td><span class="status-badge status-413">413</span></td>
            <td>Payload Too Large</td>
            <td>Request body exceeds 2 MB size limit</td>
          </tr>
          <tr>
            <td><span class="status-badge status-502">502</span></td>
            <td>Bad Gateway</td>
            <td>Modified save failed to upload back to PONOS servers. The original save may be invalidated</td>
          </tr>
          <tr>
            <td><span class="status-badge status-504">504</span></td>
            <td>Gateway Timeout</td>
            <td>PONOS server communication timed out during save download or upload</td>
          </tr>
          <tr>
            <td><span class="status-badge status-500">500</span></td>
            <td>Internal Server Error</td>
            <td>Unexpected server-side exception. The error type name is included in the message for debugging</td>
          </tr>
        </tbody>
      </table>

      <h4 class="sub-section-title">Error Response Example</h4>
      <pre class="code-block"><code>{
  "success": false,
  "message": "Invalid or expired transfer code / PIN."
}</code></pre>
    </div>
  </div>

  <h2 class="section-title">Supported Game Regions</h2>
  <div class="card">
    <div class="card-body">
      <p>The API supports all four Battle Cats game regions. Use the appropriate <code>country_code</code> value for your game version.</p>
      <table>
        <thead>
          <tr><th>Country Code</th><th>Region</th><th>App Name</th></tr>
        </thead>
        <tbody>
          <tr><td><code>kr</code></td><td>Korea</td><td>The Battle Cats KR</td></tr>
          <tr><td><code>jp</code></td><td>Japan</td><td>Nyanko Daisensou</td></tr>
          <tr><td><code>en</code></td><td>Global / English</td><td>The Battle Cats</td></tr>
          <tr><td><code>tw</code></td><td>Taiwan / Traditional Chinese</td><td>The Battle Cats TW</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <h2 class="section-title">Code Integration Examples</h2>
  <div class="card">
    <div class="card-body">
      <p>Standalone, copy-paste-ready code examples are available for 17 popular programming languages. Each example demonstrates the full <code>/info</code> &rarr; <code>/edit</code> workflow with error handling.</p>
      <div class="badge-list" style="margin-top: 1rem;">
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.py" target="_blank" class="chip">Python</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.js" target="_blank" class="chip">JavaScript</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.ts" target="_blank" class="chip">TypeScript</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.go" target="_blank" class="chip">Go</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.rs" target="_blank" class="chip">Rust</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.cpp" target="_blank" class="chip">C++</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.cs" target="_blank" class="chip">C#</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.c" target="_blank" class="chip">C</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.java" target="_blank" class="chip">Java</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.kt" target="_blank" class="chip">Kotlin</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.swift" target="_blank" class="chip">Swift</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.php" target="_blank" class="chip">PHP</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.rb" target="_blank" class="chip">Ruby</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.dart" target="_blank" class="chip">Dart</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.mojo" target="_blank" class="chip">Mojo</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.sh" target="_blank" class="chip">Shell</a>
        <a href="https://github.com/pafapafa/Battle-Cats-Save-File-Editor-API/blob/main/example.ps1" target="_blank" class="chip">PowerShell</a>
      </div>
    </div>
  </div>

  <h2 class="section-title">OpenAPI Specification</h2>
  <div class="card">
    <div class="card-body">
      <p>The full OpenAPI 3.0 machine-readable specification is available at <code>/openapi.json</code>. You can import this into Swagger UI, Postman, Insomnia, or any OpenAPI-compatible tool for automated client generation and testing.</p>
      <pre class="code-block"><code>GET /openapi.json</code></pre>
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
        "version": "1.0.5"
    })


@app.route("/info", methods=["POST"])
def inspect_save():
    try:
        data = request.get_json(silent=True) or {}
        tc = str(data.get("transfer_code") or data.get("tc") or "").strip()
        cc = str(data.get("confirmation_code") or data.get("cc") or data.get("confirmation_pin") or "").strip()
        country = str(data.get("country_code") or data.get("country") or data.get("cc_str") or "").strip()

        if not validate_inputs(tc, cc) or not country:
            return jsonify({"success": False, "message": "transfer_code, confirmation_code, and country_code are required."}), 400

        sf, sh = download_ponos_save(tc, cc, country)
        if sf is None:
            return jsonify({"success": False, "message": "Invalid or expired transfer code / PIN."}), 400

        if _check_timeout():
            return jsonify({"success": False, "message": "Request timed out."}), 504

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
    except Exception as exc:
        return jsonify({"success": False, "message": f"Internal server error: {type(exc).__name__}"}), 500


@app.route("/edit", methods=["POST"])
def edit_save():
  try:
    data = request.get_json(silent=True) or {}
    tc = str(data.get("transfer_code") or data.get("tc") or "").strip()
    cc = str(data.get("confirmation_code") or data.get("cc") or data.get("confirmation_pin") or "").strip()
    country = str(data.get("country_code") or data.get("country") or data.get("cc_str") or "").strip()

    catfood = safe_int(data.get("catfood"))
    xp = safe_int(data.get("xp"))
    normal_tickets = safe_int(data.get("normal_tickets"))
    rare_tickets = safe_int(data.get("rare_tickets"))
    platinum_tickets = safe_int(data.get("platinum_tickets"))
    legend_tickets = safe_int(data.get("legend_tickets"))
    platinum_shards = safe_int(data.get("platinum_shards"))
    np = safe_int(data.get("np"))
    leadership = safe_int(data.get("leadership"), hi=32767)

    catseyes = data.get("catseyes")
    catfruit = data.get("catfruit")
    behemoth_stones = data.get("behemoth_stones") or data.get("stones")
    catamins = data.get("catamins")
    if not catamins:
        ca = data.get("catamins_a")
        cb = data.get("catamins_b")
        cc_item = data.get("catamins_c")
        if ca is not None or cb is not None or cc_item is not None:
            catamins = {"a": ca or 0, "b": cb or 0, "c": cc_item or 0}

    battle_items = data.get("battle_items")

    gamatoto_level = safe_int(data.get("gamatoto_level"))
    gamatoto_xp = safe_int(data.get("gamatoto_xp"))
    gamatoto_helpers = data.get("gamatoto_helpers")
    gamatoto_helper_ids = data.get("gamatoto_helper_ids")
    gamatoto_helper_rarities = data.get("gamatoto_helper_rarities")
    ototo_engineers = safe_int(data.get("ototo_engineers"), hi=10)
    ototo_materials = data.get("ototo_materials")
    base_materials = data.get("base_materials")

    unlock_cats = bool(data.get("unlock_cats", False))
    unlock_cat_ids = data.get("unlock_cat_ids")
    remove_cat_ids = data.get("remove_cat_ids")

    cat_levels = data.get("cat_levels")
    cat_evolutions = data.get("cat_evolutions") or data.get("cat_forms")
    cat_forms = data.get("cat_forms")
    max_cat_levels = bool(data.get("max_cat_levels", False))
    true_form_all = bool(data.get("true_form_all", False) or data.get("max_cat_evolutions", False))

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
        catseyes is not None, catfruit is not None, behemoth_stones is not None, catamins is not None, battle_items is not None,
        gamatoto_level is not None, gamatoto_xp is not None, gamatoto_helpers, gamatoto_helper_ids, gamatoto_helper_rarities,
        ototo_engineers is not None, ototo_materials is not None, base_materials is not None,
        unlock_cats, unlock_cat_ids, remove_cat_ids,
        cat_levels, cat_evolutions, cat_forms, max_cat_levels, true_form_all,
        clear_all_stages, clear_chapters, clear_stages,
        max_treasures, max_chapter_treasures, stage_treasures
    ])

    if not has_any_edit:
        return jsonify({"success": False, "message": "At least one modification value or flag must be specified."}), 400

    sf, sh = download_ponos_save(tc, cc, country)
    if sf is None:
        return jsonify({"success": False, "message": "Invalid or expired transfer code / PIN."}), 400

    if _check_timeout():
        return jsonify({"success": False, "message": "Request timed out during save download."}), 504

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
        catseyes=catseyes,
        catfruit=catfruit,
        behemoth_stones=behemoth_stones,
        catamins=catamins,
        battle_items=battle_items,
        gamatoto_level=gamatoto_level,
        gamatoto_xp=gamatoto_xp,
        gamatoto_helpers=gamatoto_helpers,
        gamatoto_helper_ids=gamatoto_helper_ids,
        gamatoto_helper_rarities=gamatoto_helper_rarities,
        ototo_engineers=ototo_engineers,
        ototo_materials=ototo_materials,
        base_materials=base_materials,
        unlock_cats=unlock_cats,
        unlock_cat_ids=unlock_cat_ids,
        remove_cat_ids=remove_cat_ids,
        cat_levels=cat_levels,
        cat_evolutions=cat_evolutions,
        cat_forms=cat_forms,
        max_cat_levels=max_cat_levels,
        true_form_all=true_form_all,
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
  except Exception as exc:
    return jsonify({"success": False, "message": f"Internal server error: {type(exc).__name__}"}), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "message": "Endpoint not found."}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"success": False, "message": "Method not allowed."}), 405


@app.errorhandler(413)
def payload_too_large(e):
    return jsonify({"success": False, "message": "Request payload too large (max 2MB)."}), 413


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"success": False, "message": "Internal server error."}), 500
