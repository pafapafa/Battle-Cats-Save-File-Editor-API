# Battle Cats Save File Editor API Specification

The Battle Cats Save File Editor API is a high-performance RESTful cloud service that provides raw binary patching, automated PONOS server cloud transfer handling, and save file management.

---

## Base URLs

- **Live Production Endpoint**: `https://battle-cats-save-file-editor-api.vercel.app`
- **Interactive OpenAPI Specification**: `https://battle-cats-save-file-editor-api.vercel.app/docs`
- **Raw OpenAPI Schema**: `https://battle-cats-save-file-editor-api.vercel.app/openapi.json`

---

## Global Headers & Rate Limits

### Required Request Headers
- `Content-Type: application/json`
- `Accept: application/json`

### Rate Limits
- **Burst Limit**: Maximum 10 requests per minute per IP address.
- **Daily Quota**: Maximum 100 requests per 24 hours per IP address.
- **Payload Size Limit**: Maximum 2MB per request body.

---

## API Endpoints Reference

### 1. Health Check
Retrieves API operational status.

- **HTTP Method**: `GET`
- **Path**: `/`

#### Response (`200 OK`)
```json
{
  "service": "Battle Cats Save File Editor API",
  "status": "online",
  "version": "1.0.0"
}
```

---

### 2. Inspect Save File Details
Downloads save metadata from PONOS servers using a valid Transfer Code and PIN.

- **HTTP Method**: `POST`
- **Path**: `/info`

#### Request Body
```json
{
  "transfer_code": "1a2b3c4d5",
  "confirmation_code": "1234",
  "country_code": "kr"
}
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `transfer_code` | `string` | Yes | PONOS 9-digit Transfer Code |
| `confirmation_code` | `string` | Yes | PONOS 4-digit PIN Code |
| `country_code` | `string` | Yes | Region Code (`"kr"`, `"jp"`, `"en"`, `"tw"`) |

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Save info retrieved successfully.",
  "game_version": 140300,
  "catfood": 6767,
  "xp": 50000,
  "rare_tickets": 10,
  "platinum_tickets": 2,
  "legend_tickets": 1
}
```

---

### 3. Modify Save File & Re-Upload
Applies target modifications, syncs server managed items, and issues new transfer credentials.

- **HTTP Method**: `POST`
- **Path**: `/edit`

#### Request Body
```json
{
  "transfer_code": "1a2b3c4d5",
  "confirmation_code": "1234",
  "country_code": "kr",
  "catfood": 45000,
  "xp": 99999999,
  "rare_tickets": 999,
  "platinum_tickets": 99,
  "legend_tickets": 9,
  "unlock_cats": true,
  "max_treasures": true,
  "enable_safety": false
}
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `transfer_code` | `string` | Yes | PONOS 9-digit Transfer Code |
| `confirmation_code` | `string` | Yes | PONOS 4-digit PIN Code |
| `country_code` | `string` | Yes | Region Code (`"kr"`, `"jp"`, `"en"`, `"tw"`) |
| `catfood` | `integer` | No | Target Cat Food balance |
| `xp` | `integer` | No | Target XP balance |
| `rare_tickets` | `integer` | No | Target Rare Tickets count |
| `platinum_tickets` | `integer` | No | Target Platinum Tickets count |
| `legend_tickets` | `integer` | No | Target Legend Tickets count |
| `unlock_cats` | `boolean` | No | Unlock all obtainable characters |
| `max_treasures` | `boolean` | No | Set all chapter treasures to Gold |
| `enable_safety` | `boolean` | No | Clamp Cat Food (max 45k) and XP (max 100M) |

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Save modified and uploaded successfully.",
  "new_transfer_code": "9z8y7x6w5",
  "new_confirmation_code": "5678"
}
```

---

## Integration Code Examples

### cURL
```bash
curl -X POST "https://battle-cats-save-file-editor-api.vercel.app/edit" \
     -H "Content-Type: application/json" \
     -d '{
           "transfer_code": "1a2b3c4d5",
           "confirmation_code": "1234",
           "country_code": "kr",
           "catfood": 10000
         }'
```

### Python
```python
import requests

url = "https://battle-cats-save-file-editor-api.vercel.app/edit"
payload = {
    "transfer_code": "1a2b3c4d5",
    "confirmation_code": "1234",
    "country_code": "kr",
    "catfood": 10000
}

response = requests.post(url, json=payload, timeout=30)
data = response.json()

if data.get("success"):
    print("New Transfer Code:", data.get("new_transfer_code"))
    print("New Confirmation PIN:", data.get("new_confirmation_code"))
```

### JavaScript / Node.js
```javascript
const fetch = require('node-fetch');

async function editSave() {
    const response = await fetch('https://battle-cats-save-file-editor-api.vercel.app/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            transfer_code: '1a2b3c4d5',
            confirmation_code: '1234',
            country_code: 'kr',
            catfood: 10000
        })
    });
    const data = await response.json();
    console.log(data);
}

editSave();
```
