<?php
declare(strict_types=1);

const MAX_BYTES = 2097152;

function main(array $arguments): void
{
    if (count($arguments) !== 3) {
        throw new RuntimeException('Usage: php example.php REQUEST_JSON OUTPUT_SAVE');
    }
    [, $input, $output] = $arguments;
    if (file_exists($output) || is_link($output)) {
        throw new RuntimeException('Output already exists');
    }
    $base = rtrim(getenv('BCSFE_API_URL') ?: 'https://battle-cats-save-file-editor-api.vercel.app', '/');
    $url = $base . '/v2/save/edit';
    $parts = parse_url($url);
    if ($parts === false || !in_array($parts['scheme'] ?? '', ['http', 'https'], true) ||
        empty($parts['host']) || isset($parts['user'], $parts['pass']) || isset($parts['user']) ||
        isset($parts['query']) || isset($parts['fragment'])) {
        throw new RuntimeException('BCSFE_API_URL must be an HTTP(S) base URL without credentials, query, or fragment');
    }
    if (!is_file($input) || filesize($input) > MAX_BYTES) {
        throw new RuntimeException('Request must be a file of at most 2 MiB');
    }
    $body = file_get_contents($input);
    if ($body === false || strlen($body) > MAX_BYTES) {
        throw new RuntimeException('Cannot read request or request exceeds 2 MiB');
    }
    $payload = json_decode($body, true, 512, JSON_THROW_ON_ERROR);
    if (!is_array($payload) || ($payload['output'] ?? null) !== 'file' ||
        !is_string($payload['country_code'] ?? null) || !is_string($payload['save_base64'] ?? null) ||
        !is_array($payload['operations'] ?? null)) {
        throw new RuntimeException('Request needs country_code, save_base64, operations, and output:"file"');
    }
    if (!extension_loaded('curl')) {
        throw new RuntimeException('The PHP curl extension is required');
    }
    $data = '';
    $overflow = false;
    $handle = curl_init($url);
    if ($handle === false) {
        throw new RuntimeException('Cannot initialize HTTP client');
    }
    try {
        curl_setopt_array($handle, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $body,
            CURLOPT_HTTPHEADER => [
                'Content-Type: application/json',
                'Accept: application/octet-stream',
            ],
            CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_CONNECTTIMEOUT => 15,
            CURLOPT_TIMEOUT => 120,
            CURLOPT_WRITEFUNCTION => static function ($unused, string $chunk) use (&$data, &$overflow): int {
                if (strlen($data) + strlen($chunk) > MAX_BYTES) {
                    $overflow = true;
                    return 0;
                }
                $data .= $chunk;
                return strlen($chunk);
            },
        ]);
        if (curl_exec($handle) === false) {
            throw new RuntimeException($overflow ? 'Response exceeds 2 MiB' : 'HTTP request failed');
        }
        $status = curl_getinfo($handle, CURLINFO_RESPONSE_CODE);
        $contentType = strtolower(trim(explode(';', curl_getinfo($handle, CURLINFO_CONTENT_TYPE) ?: '')[0]));
        if ($status < 200 || $status >= 300 || $contentType !== 'application/octet-stream') {
            throw new RuntimeException('Expected a binary success response; HTTP ' . $status);
        }
    } finally {
        curl_close($handle);
    }
    $file = @fopen($output, 'xb');
    if ($file === false) {
        throw new RuntimeException('Cannot create output; existing files are never overwritten');
    }
    $completed = false;
    try {
        $offset = 0;
        while ($offset < strlen($data)) {
            $written = fwrite($file, substr($data, $offset));
            if ($written === false || $written === 0) {
                throw new RuntimeException('Cannot write output');
            }
            $offset += $written;
        }
        if (!fflush($file)) {
            throw new RuntimeException('Cannot flush output');
        }
        $completed = true;
    } finally {
        fclose($file);
        if (!$completed) {
            @unlink($output);
        }
    }
    fwrite(STDOUT, 'Saved ' . strlen($data) . ' bytes to ' . $output . PHP_EOL);
}

try {
    main($argv);
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . PHP_EOL);
    exit(1);
}
