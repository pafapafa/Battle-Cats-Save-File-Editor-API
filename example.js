const fs = require('node:fs');
const http = require('node:http');
const https = require('node:https');

const MAX_BYTES = 2 * 1024 * 1024;

function download(url, body) {
  return new Promise((resolve, reject) => {
    const transport = url.protocol === 'https:' ? https : http;
    const request = transport.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/octet-stream',
        'Content-Length': body.length,
      },
    });
    const totalTimer = setTimeout(() => request.destroy(new Error('Request timed out')), 120000);
    const connectTimer = setTimeout(() => request.destroy(new Error('Connection timed out')), 15000);
    function cleanup() {
      clearTimeout(totalTimer);
      clearTimeout(connectTimer);
    }
    request.on('socket', (socket) => {
      socket.once(url.protocol === 'https:' ? 'secureConnect' : 'connect', () => clearTimeout(connectTimer));
    });
    request.once('error', (error) => {
      cleanup();
      reject(error);
    });
    request.once('response', (response) => {
      const status = response.statusCode || 0;
      const contentType = (response.headers['content-type'] || '').split(';')[0].trim().toLowerCase();
      if (status < 200 || status >= 300 || contentType !== 'application/octet-stream') {
        request.destroy(new Error(`Expected a binary success response; HTTP ${status}`));
        return;
      }
      const chunks = [];
      let size = 0;
      response.on('data', (chunk) => {
        size += chunk.length;
        if (size > MAX_BYTES) {
          request.destroy(new Error('Response exceeds 2 MiB'));
          return;
        }
        chunks.push(chunk);
      });
      response.once('error', (error) => {
        cleanup();
        reject(error);
      });
      response.once('end', () => {
        cleanup();
        resolve(Buffer.concat(chunks));
      });
    });
    request.end(body);
  });
}

async function main() {
  if (process.argv.length !== 4) throw new Error('Usage: node example.js REQUEST_JSON OUTPUT_SAVE');
  const [input, output] = process.argv.slice(2);
  try {
    fs.lstatSync(output);
    throw new Error('Output already exists');
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  const base = (process.env.BCSFE_API_URL || 'https://battle-cats-save-file-editor-api.vercel.app').replace(/\/+$/, '');
  const url = new URL(`${base}/v2/save/edit`);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error('BCSFE_API_URL must be an HTTP(S) base URL without credentials, query, or fragment');
  }
  if (fs.statSync(input).size > MAX_BYTES) throw new Error('Request exceeds 2 MiB');
  const body = fs.readFileSync(input);
  if (body.length > MAX_BYTES) throw new Error('Request exceeds 2 MiB');
  let payload;
  try {
    payload = JSON.parse(body.toString('utf8'));
  } catch {
    throw new Error('Request must be valid UTF-8 JSON');
  }
  if (!payload || typeof payload !== 'object' || payload.output !== 'file' ||
      typeof payload.country_code !== 'string' || typeof payload.save_base64 !== 'string' || !Array.isArray(payload.operations)) {
    throw new Error('Request needs country_code, save_base64, operations, and output:"file"');
  }
  const data = await download(url, body);
  let descriptor;
  let created = false;
  try {
    descriptor = fs.openSync(output, 'wx', 0o600);
    created = true;
    fs.writeFileSync(descriptor, data);
    fs.closeSync(descriptor);
    descriptor = undefined;
  } catch (error) {
    if (descriptor !== undefined) fs.closeSync(descriptor);
    if (created) fs.unlinkSync(output);
    throw error;
  }
  console.log(`Saved ${data.length} bytes to ${output}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
