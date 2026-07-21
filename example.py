import requests

url = "https://battle-cats-save-file-editor-api.vercel.app/edit"
payload = {
    "transfer_code": "1a2b3c4d5",
    "confirmation_code": "1234",
    "country_code": "kr",
    "catfood": 45000,
    "unlock_cat_ids": [0, 1, 555],
    "clear_chapters": [0, 1, 2],
    "max_treasures": True
}

response = requests.post(url, json=payload, timeout=45)
data = response.json()

if data.get("success"):
    print("Transfer Code:", data.get("transfer_code"))
    print("Confirmation PIN:", data.get("confirmation_code"))
else:
    print("Error:", data.get("message"))
