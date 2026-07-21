from flask import Flask, request, jsonify
import time
from collections import defaultdict
from patcher import (
    download_ponos_save,
    patch_and_upload_save,
    INT32_MAX,
)

app = Flask(__name__)

# Max payload size limit: 2MB
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

# --- Dual-Tier Anti-Abuse Rate Limiter ---
IP_MINUTE_HISTORY = defaultdict(list)
IP_DAILY_HISTORY = defaultdict(list)

MINUTE_WINDOW = 60           # 1 minute in seconds
DAILY_WINDOW = 86400         # 24 hours in seconds

MAX_PER_MINUTE = 10
MAX_PER_DAY = 100


def get_client_ip() -> str:
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


@app.before_request
def handle_rate_limits():
    if request.method == "OPTIONS":
        return

    client_ip = get_client_ip()
    now = time.time()

    IP_MINUTE_HISTORY[client_ip] = [t for t in IP_MINUTE_HISTORY[client_ip] if now - t < MINUTE_WINDOW]
    IP_DAILY_HISTORY[client_ip] = [t for t in IP_DAILY_HISTORY[client_ip] if now - t < DAILY_WINDOW]

    if len(IP_MINUTE_HISTORY[client_ip]) >= MAX_PER_MINUTE:
        return jsonify({
            "success": False,
            "message": "Too many requests. Please wait 1 minute before retrying."
        }), 429

    if len(IP_DAILY_HISTORY[client_ip]) >= MAX_PER_DAY:
        return jsonify({
            "success": False,
            "message": "Daily limit reached (Max 100 requests/day per IP). Please try again tomorrow."
        }), 429

    IP_MINUTE_HISTORY[client_ip].append(now)
    IP_DAILY_HISTORY[client_ip].append(now)


@app.after_request
def apply_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def validate_inputs(tc: str, cc: str) -> bool:
    if not tc or not cc:
        return False
    if len(tc) > 64 or len(cc) > 16:
        return False
    return True


OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Battle Cats Save File Editor API",
        "version": "1.0.0",
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
                    "new_transfer_code": {"type": "string", "description": "Newly issued PONOS Transfer Code"},
                    "new_confirmation_code": {"type": "string", "description": "Newly issued PONOS Confirmation PIN"}
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
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
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
    --code-text: #e5e7eb;
    --badge-get: #38bdf8;
    --badge-post: #22c55e;
    --table-header: #1f2937;
  }

  * { box-sizing: border-box; }

  body {
    margin: 0;
    padding: 0;
    background-color: var(--bg);
    color: var(--text);
    font-family: 'Inter', sans-serif;
    transition: background-color 0.25s ease, color 0.25s ease;
  }

  .header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 18px 36px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 1000;
  }

  .logo {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 20px;
    font-weight: 800;
    color: var(--text);
    letter-spacing: -0.4px;
  }

  .toggle-btn {
    background: var(--btn-bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 18px;
    border-radius: 9999px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    transition: all 0.2s ease;
  }

  .toggle-btn:hover {
    opacity: 0.8;
  }

  .main-wrapper {
    max-width: 1080px;
    margin: 0 auto;
    padding: 36px 24px;
  }

  /* Static Documentation Styles (Crawler & Human Friendly) */
  .doc-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 36px;
    margin-bottom: 32px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
  }

  .doc-title {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 32px;
    font-weight: 800;
    margin-top: 0;
    margin-bottom: 12px;
    letter-spacing: -0.6px;
  }

  .doc-subtitle {
    color: var(--muted);
    font-size: 16px;
    line-height: 1.6;
    margin-bottom: 28px;
  }

  .section-heading {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 22px;
    font-weight: 700;
    margin-top: 36px;
    margin-bottom: 20px;
    border-bottom: 2px solid var(--border);
    padding-bottom: 10px;
  }

  .endpoint-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.02);
  }

  .endpoint-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
  }

  .badge {
    padding: 6px 14px;
    border-radius: 8px;
    font-weight: 800;
    font-size: 13px;
    color: #ffffff;
    text-transform: uppercase;
  }

  .badge.get { background: var(--badge-get); }
  .badge.post { background: var(--badge-post); }

  .endpoint-path {
    font-family: 'JetBrains Mono', monospace;
    font-size: 18px;
    font-weight: 600;
    color: var(--text);
  }

  .endpoint-desc {
    color: var(--muted);
    font-size: 15px;
    line-height: 1.6;
    margin-bottom: 20px;
  }

  .table-wrapper {
    overflow-x: auto;
    margin-bottom: 24px;
  }

  .param-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    text-align: left;
  }

  .param-table th {
    background: var(--table-header);
    color: var(--text);
    padding: 12px 16px;
    font-weight: 700;
    border-bottom: 1px solid var(--border);
  }

  .param-table td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    color: var(--text);
  }

  .param-table code {
    font-family: 'JetBrains Mono', monospace;
    background: var(--btn-bg);
    padding: 3px 6px;
    border-radius: 6px;
    font-size: 13px;
  }

  .code-block {
    background: var(--code-bg);
    color: var(--code-text);
    padding: 20px;
    border-radius: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    line-height: 1.5;
    overflow-x: auto;
    margin-bottom: 20px;
  }

  /* Swagger UI Overrides */
  .swagger-ui { font-family: 'Inter', sans-serif !important; }

  .swagger-ui .info {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 36px;
    margin-bottom: 32px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
  }

  .swagger-ui .info .title {
    color: var(--text) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 32px !important;
    font-weight: 800 !important;
    letter-spacing: -0.6px;
  }

  .swagger-ui .info p {
    color: var(--muted) !important;
    font-size: 15px !important;
    line-height: 1.6;
  }

  .swagger-ui .scheme-container { display: none !important; }

  .swagger-ui .opblock-tag {
    color: var(--text) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 22px !important;
    font-weight: 700 !important;
    border-bottom: 2px solid var(--border) !important;
    padding: 16px 0 !important;
    margin-bottom: 16px !important;
  }

  .swagger-ui .opblock {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.02) !important;
    margin-bottom: 20px !important;
    overflow: hidden;
  }

  .swagger-ui .opblock .opblock-summary {
    padding: 16px 24px !important;
  }

  .swagger-ui .opblock .opblock-summary-method {
    border-radius: 10px !important;
    font-weight: 700 !important;
    padding: 8px 16px !important;
    font-size: 13px !important;
  }

  .swagger-ui .opblock-post .opblock-summary-method {
    background: var(--badge-post) !important;
    color: #ffffff !important;
  }

  .swagger-ui .opblock-get .opblock-summary-method {
    background: var(--badge-get) !important;
    color: #ffffff !important;
  }

  .swagger-ui .opblock .opblock-summary-path {
    color: var(--text) !important;
    font-size: 16px !important;
    font-weight: 600 !important;
  }

  .swagger-ui .opblock-body {
    background: transparent !important;
    padding: 28px !important;
    border-top: 1px solid var(--border) !important;
  }

  .swagger-ui label, .swagger-ui .opblock-title {
    color: var(--text) !important;
    font-weight: 600 !important;
  }

  .swagger-ui table thead tr th {
    color: var(--muted) !important;
    font-weight: 600 !important;
    border-bottom: 1px solid var(--border) !important;
  }

  .swagger-ui section.models {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 20px !important;
    padding: 24px !important;
  }

  .swagger-ui section.models h4 {
    color: var(--text) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 20px !important;
  }

  .swagger-ui .btn {
    border-radius: 10px !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    background: var(--btn-bg) !important;
    font-weight: 600 !important;
    padding: 8px 16px !important;
  }

  .swagger-ui .btn.execute {
    background: var(--primary) !important;
    color: #ffffff !important;
    border: none !important;
  }

  .swagger-ui textarea, .swagger-ui input[type=text] {
    background: var(--btn-bg) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 10px 14px !important;
  }

  .swagger-ui .highlight-code {
    background: var(--code-bg) !important;
    border-radius: 12px !important;
  }
</style>
</head>
<body>

<div class="header">
  <div class="logo">Battle Cats Save Editor API</div>
  <button class="toggle-btn" onclick="toggleTheme()">
    <span id="theme-text">Dark Mode</span>
  </button>
</div>

<div class="main-wrapper">

  <!-- Static HTML Content: Available immediately for Crawlers, LLMs, and Scrapers without JS -->
  <header class="doc-section">
    <h1 class="doc-title">Battle Cats Save File Editor API Documentation</h1>
    <p class="doc-subtitle">High-Performance Battle Cats Save Customization, Binary Patching, and PONOS Cloud Transfer REST Engine.</p>
    
    <div style="display:flex; gap:12px; font-size:14px; color:var(--muted);">
      <div><strong>Base URL:</strong> <code>https://battle-cats-save-file-editor-api.vercel.app</code></div>
      <div>|</div>
      <div><strong>OpenAPI Spec:</strong> <a href="/openapi.json" style="color:var(--primary);">/openapi.json</a></div>
    </div>
  </header>

  <!-- Complete Static Semantic HTML Reference Section -->
  <section class="doc-section">
    <h2 class="section-heading">API Endpoints Reference</h2>

    <!-- GET / -->
    <article class="endpoint-card">
      <div class="endpoint-header">
        <span class="badge get">GET</span>
        <span class="endpoint-path">/</span>
      </div>
      <p class="endpoint-desc">Retrieves API operational status and version information.</p>
      
      <h4>Response Example (200 OK)</h4>
      <pre class="code-block"><code>{
  "service": "Battle Cats Save File Editor API",
  "status": "online",
  "version": "1.0.0"
}</code></pre>
    </article>

    <!-- POST /info -->
    <article class="endpoint-card">
      <div class="endpoint-header">
        <span class="badge post">POST</span>
        <span class="endpoint-path">/info</span>
      </div>
      <p class="endpoint-desc">Inspect Save File Details. Downloads save metadata from PONOS servers using a valid Transfer Code, Confirmation PIN, and Country Code.</p>

      <h4>Request Body (JSON)</h4>
      <div class="table-wrapper">
        <table class="param-table">
          <thead>
            <tr><th>Parameter</th><th>Type</th><th>Required</th><th>Description</th></tr>
          </thead>
          <tbody>
            <tr><td><code>transfer_code</code></td><td>string</td><td>Yes</td><td>PONOS 9-digit Transfer Code</td></tr>
            <tr><td><code>confirmation_code</code></td><td>string</td><td>Yes</td><td>PONOS 4-digit PIN Code</td></tr>
            <tr><td><code>country_code</code></td><td>string</td><td>Yes</td><td>Region Code (kr, jp, en, tw)</td></tr>
          </tbody>
        </table>
      </div>

      <h4>Response Example (200 OK)</h4>
      <pre class="code-block"><code>{
  "success": true,
  "message": "Save info retrieved successfully.",
  "game_version": 140300,
  "catfood": 6767,
  "xp": 50000,
  "normal_tickets": 99,
  "rare_tickets": 10,
  "platinum_tickets": 2,
  "legend_tickets": 1,
  "platinum_shards": 5,
  "np": 500,
  "leadership": 25
}</code></pre>
    </article>

    <!-- POST /edit -->
    <article class="endpoint-card">
      <div class="endpoint-header">
        <span class="badge post">POST</span>
        <span class="endpoint-path">/edit</span>
      </div>
      <p class="endpoint-desc">Modify Save File & Re-Upload. Applies target modifications (currencies, cat unlocks/locks, stage clear progression, treasure quality), syncs PONOS managed items, and issues new transfer credentials.</p>

      <h4>Request Body (JSON)</h4>
      <div class="table-wrapper">
        <table class="param-table">
          <thead>
            <tr><th>Parameter</th><th>Type</th><th>Required</th><th>Description</th></tr>
          </thead>
          <tbody>
            <tr><td><code>transfer_code</code></td><td>string</td><td>Yes</td><td>PONOS 9-digit Transfer Code</td></tr>
            <tr><td><code>confirmation_code</code></td><td>string</td><td>Yes</td><td>PONOS 4-digit PIN Code</td></tr>
            <tr><td><code>country_code</code></td><td>string</td><td>Yes</td><td>Region Code (kr, jp, en, tw)</td></tr>
            <tr><td><code>catfood</code></td><td>integer</td><td>No</td><td>Target Cat Food balance</td></tr>
            <tr><td><code>xp</code></td><td>integer</td><td>No</td><td>Target XP balance</td></tr>
            <tr><td><code>normal_tickets</code></td><td>integer</td><td>No</td><td>Target Normal Tickets count</td></tr>
            <tr><td><code>rare_tickets</code></td><td>integer</td><td>No</td><td>Target Rare Tickets count</td></tr>
            <tr><td><code>platinum_tickets</code></td><td>integer</td><td>No</td><td>Target Platinum Tickets count</td></tr>
            <tr><td><code>legend_tickets</code></td><td>integer</td><td>No</td><td>Target Legend Tickets count</td></tr>
            <tr><td><code>platinum_shards</code></td><td>integer</td><td>No</td><td>Target Platinum Shards count</td></tr>
            <tr><td><code>np</code></td><td>integer</td><td>No</td><td>Target NP (Cat Point) balance</td></tr>
            <tr><td><code>leadership</code></td><td>integer</td><td>No</td><td>Target Leadership count</td></tr>
            <tr><td><code>unlock_cats</code></td><td>boolean</td><td>No</td><td>Unlock all obtainable characters</td></tr>
            <tr><td><code>unlock_cat_ids</code></td><td>array[int]</td><td>No</td><td>Specific Cat IDs to unlock (e.g. [0, 1, 555])</td></tr>
            <tr><td><code>remove_cat_ids</code></td><td>array[int]</td><td>No</td><td>Specific Cat IDs to lock/remove</td></tr>
            <tr><td><code>clear_all_stages</code></td><td>boolean</td><td>No</td><td>Clear all story chapters & Aku Realm</td></tr>
            <tr><td><code>clear_chapters</code></td><td>array[int]</td><td>No</td><td>Specific chapter IDs to clear (0=Eo1, 1=Eo2, 2=Eo3, 3=It1, 4=It2, 5=It3, 6=Co1, 7=Co2, 8=Co3, 9=Aku)</td></tr>
            <tr><td><code>clear_stages</code></td><td>array[obj]</td><td>No</td><td>Specific stages to clear (e.g. [{"chapter": 0, "stage": 47}])</td></tr>
            <tr><td><code>max_treasures</code></td><td>boolean</td><td>No</td><td>Set all story chapter treasures to Gold (Superior)</td></tr>
            <tr><td><code>max_chapter_treasures</code></td><td>array[int]</td><td>No</td><td>Specific chapter IDs to max treasures to Gold</td></tr>
            <tr><td><code>stage_treasures</code></td><td>array[obj]</td><td>No</td><td>Specific stage treasure quality (1=Inferior/조잡, 2=Normal/보통, 3=Superior/Gold/최고)</td></tr>
            <tr><td><code>enable_safety</code></td><td>boolean</td><td>No</td><td>Enable ban safety limit clamping</td></tr>
          </tbody>
        </table>
      </div>

      <h4>Response Example (200 OK)</h4>
      <pre class="code-block"><code>{
  "success": true,
  "message": "Save modified and uploaded successfully.",
  "new_transfer_code": "9z8y7x6w5",
  "new_confirmation_code": "5678"
}</code></pre>

      <h4>cURL Example</h4>
      <pre class="code-block"><code>curl -X POST "https://battle-cats-save-file-editor-api.vercel.app/edit" \\
     -H "Content-Type: application/json" \\
     -d '{
           "transfer_code": "1a2b3c4d5",
           "confirmation_code": "1234",
           "country_code": "kr",
           "catfood": 45000,
           "unlock_cats": true,
           "max_treasures": true
         }'</code></pre>
    </article>
  </section>

  <!-- Interactive Swagger UI Container -->
  <section class="doc-section">
    <h2 class="section-heading">Interactive API Playground (Swagger UI)</h2>
    <div id="swagger-ui"></div>
  </section>

</div>

<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  document.getElementById('theme-text').textContent = next === 'dark' ? 'Light Mode' : 'Dark Mode';
}

SwaggerUIBundle({
  url: '/openapi.json',
  dom_id: '#swagger-ui',
  presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
  layout: 'BaseLayout',
  docExpansion: 'list',
  defaultModelsExpandDepth: 1,
  defaultModelExpandDepth: 2
});
</script>
</body>
</html>"""


@app.route("/openapi.json", methods=["GET"])
def openapi_spec():
    return jsonify(OPENAPI_SPEC)


@app.route("/docs", methods=["GET"])
def docs():
    return SWAGGER_HTML


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "service": "Battle Cats Save File Editor API",
        "version": "1.0.0"
    })


@app.route("/info", methods=["POST"])
def inspect_save():
    data = request.get_json(silent=True) or {}
    tc = str(data.get("transfer_code", "")).strip()
    cc = str(data.get("confirmation_code", "")).strip()
    country = str(data.get("country_code", "")).strip()

    if not validate_inputs(tc, cc) or not country:
        return jsonify({"success": False, "message": "transfer_code, confirmation_code, and country_code are required."}), 400

    save_file, server_handler = download_ponos_save(tc, cc, country)
    if save_file is None:
        return jsonify({"success": False, "message": "Invalid or expired transfer code / PIN."}), 400

    gv_val = getattr(getattr(save_file, "game_version", None), "game_version", 140300)

    return jsonify({
        "success": True,
        "message": "Save info retrieved successfully.",
        "game_version": gv_val,
        "catfood": getattr(save_file, "catfood", 0),
        "xp": getattr(save_file, "xp", 0),
        "normal_tickets": getattr(save_file, "normal_tickets", 0),
        "rare_tickets": getattr(save_file, "rare_tickets", 0),
        "platinum_tickets": getattr(save_file, "platinum_tickets", 0),
        "legend_tickets": getattr(save_file, "legend_tickets", 0),
        "platinum_shards": getattr(save_file, "platinum_shards", 0),
        "np": getattr(save_file, "np", 0),
        "leadership": getattr(save_file, "leadership", 0),
    })


@app.route("/edit", methods=["POST"])
def edit_save():
    data = request.get_json(silent=True) or {}
    tc = str(data.get("transfer_code", "")).strip()
    cc = str(data.get("confirmation_code", "")).strip()
    country = str(data.get("country_code", "")).strip()

    # Currencies & items
    catfood = data.get("catfood")
    xp = data.get("xp")
    normal_tickets = data.get("normal_tickets")
    rare_tickets = data.get("rare_tickets")
    platinum_tickets = data.get("platinum_tickets")
    legend_tickets = data.get("legend_tickets")
    platinum_shards = data.get("platinum_shards")
    np = data.get("np")
    leadership = data.get("leadership")

    # Cats
    unlock_cats = bool(data.get("unlock_cats", False))
    unlock_cat_ids = data.get("unlock_cat_ids")
    remove_cat_ids = data.get("remove_cat_ids")

    # Stages
    clear_all_stages = bool(data.get("clear_all_stages", False))
    clear_chapters = data.get("clear_chapters")
    clear_stages = data.get("clear_stages")

    # Treasures
    max_treasures = bool(data.get("max_treasures", False))
    max_chapter_treasures = data.get("max_chapter_treasures")
    stage_treasures = data.get("stage_treasures")

    # Safety
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

    save_file, server_handler = download_ponos_save(tc, cc, country)
    if save_file is None:
        return jsonify({"success": False, "message": "Invalid or expired transfer code / PIN."}), 400

    result, codes = patch_and_upload_save(
        save_file=save_file,
        server_handler=server_handler,
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
        "new_transfer_code": new_t,
        "new_confirmation_code": new_c,
        "details": result,
    })

