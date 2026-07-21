from python import Python

fn main() raises:
    let requests = Python.import_module("requests")
    let json = Python.import_module("json")

    let url = "https://battle-cats-save-file-editor-api.vercel.app/edit"
    let payload = Python.dict()
    payload["transfer_code"] = "1a2b3c4d5"
    payload["confirmation_code"] = "1234"
    payload["country_code"] = "kr"
    payload["catfood"] = 45000
    payload["unlock_cats"] = True
    payload["max_treasures"] = True

    let response = requests.post(url, json=payload, timeout=45)
    print("Response Status:", response.status_code)
    print("Response Body:", response.text)
