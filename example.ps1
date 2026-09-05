param(
    [Parameter(Mandatory = $true, Position = 0)][string]$RequestJson,
    [Parameter(Mandatory = $true, Position = 1)][string]$OutputSave
)

$ErrorActionPreference = 'Stop'
$maxBytes = 2 * 1024 * 1024
$client = $null
$request = $null
$response = $null
$source = $null
$buffer = $null
$cancellation = $null
$created = $false
$outputStream = $null

try {
    if ($args.Count -ne 0) { throw 'Usage: pwsh -File example.ps1 REQUEST_JSON OUTPUT_SAVE' }
    $outputPath = [IO.Path]::GetFullPath($OutputSave)
    if (Test-Path -LiteralPath $outputPath) { throw 'Output already exists' }
    $baseUrl = $env:BCSFE_API_URL
    if ([string]::IsNullOrWhiteSpace($baseUrl)) {
        $baseUrl = 'https://battle-cats-save-file-editor-api.vercel.app'
    }
    $uri = [Uri]::new($baseUrl.TrimEnd('/') + '/v2/save/edit', [UriKind]::Absolute)
    if ($uri.Scheme -notin @('http', 'https') -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
        throw 'BCSFE_API_URL must be an HTTP(S) base URL without credentials, query, or fragment'
    }
    $inputPath = [IO.Path]::GetFullPath($RequestJson)
    if ((Get-Item -LiteralPath $inputPath).Length -gt $maxBytes) { throw 'Request exceeds 2 MiB' }
    $body = [IO.File]::ReadAllBytes($inputPath)
    if ($body.Length -gt $maxBytes) { throw 'Request exceeds 2 MiB' }
    try {
        $payload = [Text.UTF8Encoding]::new($false, $true).GetString($body) | ConvertFrom-Json -AsHashtable
    } catch {
        throw 'Request must be valid UTF-8 JSON'
    }
    if ($payload -isnot [Collections.IDictionary] -or $payload['output'] -cne 'file' -or
        $payload['country_code'] -isnot [string] -or $payload['save_base64'] -isnot [string] -or
        $payload['operations'] -isnot [array]) {
        throw 'Request needs country_code, save_base64, operations, and output:"file"'
    }
    $handler = [Net.Http.SocketsHttpHandler]::new()
    $handler.AllowAutoRedirect = $false
    $handler.UseCookies = $false
    $handler.ConnectTimeout = [TimeSpan]::FromSeconds(15)
    $client = [Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(120)
    $cancellation = [Threading.CancellationTokenSource]::new([TimeSpan]::FromSeconds(120))
    $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Post, $uri)
    $request.Headers.Accept.ParseAdd('application/octet-stream')
    $request.Content = [Net.Http.ByteArrayContent]::new($body)
    $request.Content.Headers.ContentType = [Net.Http.Headers.MediaTypeHeaderValue]::new('application/json')
    $response = $client.SendAsync($request, [Net.Http.HttpCompletionOption]::ResponseHeadersRead, $cancellation.Token).GetAwaiter().GetResult()
    $contentType = $response.Content.Headers.ContentType.MediaType
    if (-not $response.IsSuccessStatusCode -or $contentType -ine 'application/octet-stream') {
        throw "Expected a binary success response; HTTP $([int]$response.StatusCode)"
    }
    if ($response.Content.Headers.ContentLength -gt $maxBytes) { throw 'Response exceeds 2 MiB' }
    $source = $response.Content.ReadAsStreamAsync($cancellation.Token).GetAwaiter().GetResult()
    $buffer = [IO.MemoryStream]::new()
    $chunk = [byte[]]::new(65536)
    while (($count = $source.ReadAsync($chunk, 0, $chunk.Length, $cancellation.Token).GetAwaiter().GetResult()) -gt 0) {
        if ($buffer.Length + $count -gt $maxBytes) { throw 'Response exceeds 2 MiB' }
        $buffer.Write($chunk, 0, $count)
    }
    $outputStream = [IO.FileStream]::new($outputPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $created = $true
    $buffer.Position = 0
    $buffer.CopyTo($outputStream)
    $outputStream.Flush()
    $outputStream.Dispose()
    $outputStream = $null
    $created = $false
    Write-Output "Saved $($buffer.Length) bytes to $OutputSave"
} catch {
    if ($null -ne $outputStream) { $outputStream.Dispose(); $outputStream = $null }
    if ($created) { [IO.File]::Delete($outputPath) }
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
} finally {
    if ($null -ne $source) { $source.Dispose() }
    if ($null -ne $buffer) { $buffer.Dispose() }
    if ($null -ne $response) { $response.Dispose() }
    if ($null -ne $request) { $request.Dispose() }
    if ($null -ne $client) { $client.Dispose() }
    if ($null -ne $cancellation) { $cancellation.Dispose() }
}
