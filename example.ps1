$url = "https://battle-cats-save-file-editor-api.vercel.app/edit"
$body = @{
    transfer_code     = "1a2b3c4d5"
    confirmation_code = "1234"
    country_code      = "kr"
    catfood           = 45000
    unlock_cats       = $true
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json" -Body $body
$response | ConvertTo-Json
