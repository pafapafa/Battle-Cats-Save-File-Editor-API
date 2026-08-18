# Battle Cats Save File Editor API Specification (v1.1.0)

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
  "version": "1.0.3"
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
  "unban_account": true,
  "fix_time_errors": true,
  "rare_gatya_seed": 123456789
}
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `transfer_code` | `string` | Yes | PONOS 9-digit Transfer Code |
| `confirmation_code` | `string` | Yes | PONOS 4-digit PIN Code |
| `country_code` | `string` | Yes | Region Code (`"kr"`, `"jp"`, `"en"`, `"tw"`) |
| `catfood` | `integer` | No | Target Cat Food balance |
| `xp` | `integer` | No | Target XP balance |
| `normal_tickets` | `integer` | No | Target Normal Tickets count |
| `rare_tickets` | `integer` | No | Target Rare Tickets count |
| `platinum_tickets` | `integer` | No | Target Platinum Tickets count |
| `legend_tickets` | `integer` | No | Target Legend Tickets count |
| `platinum_shards` | `integer` | No | Target Platinum Shards count |
| `np` | `integer` | No | Target NP balance |
| `leadership` | `integer` | No | Target Leadership count |
| `catseyes` | `integer / array` | No | Target Catseye count (all types or `[EX, Rare, S.Rare, U.Rare, Legend]`) |
| `catfruit` | `integer / array` | No | Target Catfruit / Matatabi count |
| `catamins` | `integer / array` | No | Target Catamins A/B/C count |
| `gamatoto_level` | `integer` | No | Target Gamatoto Level (e.g. `150`) |
| `gamatoto_xp` | `integer` | No | Target Gamatoto XP value |
| `gamatoto_helpers` | `boolean` | No | Set all 10 Gamatoto helpers to Legend/Master rarity |
| `ototo_engineers` | `integer` | No | Target Ototo engineer count (max 10) |
| `unlock_cats` | `boolean` | No | Unlock all obtainable characters |
| `unlock_cat_ids` | `array[int]` | No | Specific Cat IDs to unlock (e.g. `[0, 1, 555]`) |
| `remove_cat_ids` | `array[int]` | No | Specific Cat IDs to lock/remove |
| `clear_all_stages` | `boolean` | No | Clear all story chapters & Aku Realm |
| `clear_chapters` | `array[int]` | No | Specific chapter IDs to clear (0 to 9) |
| `clear_stages` | `array[object]` | No | Specific stages to clear (e.g. `[{"chapter": 0, "stage": 47}]`) |
| `max_treasures` | `boolean` | No | Set all story chapter treasures to Superior |
| `max_chapter_treasures` | `array[int]` | No | Specific chapter IDs to max treasures to Superior |
| `stage_treasures` | `array[object]` | No | Specific stage treasure quality (`1` = Inferior, `2` = Normal, `3` = Superior) |
| `unban_account` | `boolean` | No | Unban the account (remove ban flag) |
| `fix_time_errors` | `boolean` | No | Fix HGT/time errors and enable events |
| `fix_gamatoto_crash` | `boolean` | No | Fix Gamatoto expedition crashes |
| `fix_ototo_crash` | `boolean` | No | Fix Ototo corps/development crashes |
| `unlock_equip_menu` | `boolean` | No | Unlock the equip menu if it's missing |
| `upload_items` | `boolean` | No | Force sync and upload current items to server |
| `rare_gatya_seed` | `integer` | No | Set the Rare Gatya seed value |
| `normal_gatya_seed` | `integer` | No | Set the Normal Gatya seed value |
| `event_gatya_seed` | `integer` | No | Set the Event Gatya seed value |
| `claim_all_rewards` | `boolean` | No | Claim all available mission/login rewards |
| `max_special_skills` | `boolean` | No | Max out all 10 base abilities (cannon, wallet, etc) |
| `max_all_talents` | `boolean` | No | Max out talents and ultra talents for all cats |
| `max_talent_orbs` | `boolean` | No | Set all talent orbs to 99 |
| `max_castle_development` | `boolean` | No | Max out all Ototo castle development and materials |
| `enable_safety` | `boolean` | No | Clamp Cat Food (max 45k) and XP (max 100M) |

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Save modified and uploaded successfully.",
  "transfer_code": "9z8y7x6w5",
  "confirmation_code": "5678"
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
           "unban_account": true,
           "fix_time_errors": true
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
    "rare_gatya_seed": 123456789
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
            unban_account: true
        })
    });
    const data = await response.json();
    console.log(data);
}

editSave();
```
