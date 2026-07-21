use std::collections::HashMap;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = reqwest::Client::new();
    let url = "https://battle-cats-save-file-editor-api.vercel.app/edit";

    let mut body = HashMap::new();
    body.insert("transfer_code", "1a2b3c4d5");
    body.insert("confirmation_code", "1234");
    body.insert("country_code", "kr");

    let response = client.post(url)
        .header("Content-Type", "application/json")
        .json(&body)
        .send()
        .await?;

    let text = response.text().await?;
    println!("Response: {}", text);

    Ok(())
}
