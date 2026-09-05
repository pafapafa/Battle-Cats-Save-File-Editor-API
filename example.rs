use reqwest::blocking::Client;
use reqwest::header::{ACCEPT, CONTENT_TYPE};
use reqwest::redirect::Policy;
use std::env;
use std::error::Error;
use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::path::Path;
use std::time::Duration;

const LIMIT: usize = 2 * 1024 * 1024;

fn setting(name: &str, fallback: &str) -> String {
    env::var(name).ok().filter(|value| !value.is_empty()).unwrap_or_else(|| fallback.to_string())
}

fn run() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = env::args_os().skip(1).collect();
    if args.len() != 2 {
        return Err("Usage: example REQUEST_JSON OUTPUT_SAVE".into());
    }
    let output_path = Path::new(&args[1]);
    if output_path.try_exists()? {
        return Err("Output already exists; choose a new path.".into());
    }
    let length = fs::metadata(&args[0])?.len();
    if length == 0 || length > LIMIT as u64 {
        return Err("Request must be 1 byte to 2 MiB.".into());
    }
    let payload = fs::read(&args[0])?;
    let base = setting("BCSFE_API_URL", "https://battle-cats-save-file-editor-api.vercel.app");
    let url = format!("{}/v2/save/edit", base.trim_end_matches('/'));
    let client = Client::builder()
        .connect_timeout(Duration::from_secs(15))
        .timeout(Duration::from_secs(120))
        .redirect(Policy::none())
        .build()?;
    let response = client.post(url)
        .header(CONTENT_TYPE, "application/json")
        .header(ACCEPT, "application/octet-stream")
        .body(payload)
        .send()?;
    if !response.status().is_success() {
        return Err(format!("API returned HTTP {}. No save was written.", response.status()).into());
    }
    let content_type = response.headers().get(CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .unwrap_or("").split(';').next().unwrap_or("").trim();
    if !content_type.eq_ignore_ascii_case("application/octet-stream") {
        return Err("Expected a binary save; set output to file in the request JSON.".into());
    }
    let mut save = Vec::new();
    response.take((LIMIT + 1) as u64).read_to_end(&mut save)?;
    if save.is_empty() || save.len() > LIMIT {
        return Err("Response is empty or exceeds 2 MiB.".into());
    }
    let mut output = OpenOptions::new().write(true).create_new(true).open(output_path)?;
    if let Err(error) = output.write_all(&save).and_then(|_| output.sync_all()) {
        drop(output);
        let _ = fs::remove_file(output_path);
        return Err(error.into());
    }
    drop(output);
    println!("Saved {} bytes to {}", save.len(), output_path.display());
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}