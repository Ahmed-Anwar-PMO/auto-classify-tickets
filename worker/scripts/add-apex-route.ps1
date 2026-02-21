# Add myaleena.com/* route to Cloudflare Worker (bypasses wrangler deploy)
# Run: $env:CLOUDFLARE_API_TOKEN = "your-token"; .\add-apex-route.ps1
# Or: .\add-apex-route.ps1 -Token "your-token"

param(
    [string]$Token = $env:CLOUDFLARE_API_TOKEN,
    [string]$ZoneId = "e61e1e99902f88e8a21ecb3419e23465",
    [string]$WorkerName = "zendesk-ticket-classifier"
)

if (-not $Token) {
    Write-Error "Set CLOUDFLARE_API_TOKEN or pass -Token 'your-token'"
    exit 1
}

$uri = "https://api.cloudflare.com/client/v4/zones/$ZoneId/workers/routes"
$body = @{
    pattern = "myaleena.com/*"
    script  = $WorkerName
} | ConvertTo-Json

$headers = @{
    "Authorization" = "Bearer $Token"
    "Content-Type"  = "application/json"
}

try {
    $existing = Invoke-RestMethod -Uri $uri -Method Get -Headers $headers
    $apex = $existing.result | Where-Object { $_.pattern -eq "myaleena.com/*" }
    if ($apex) {
        Write-Host "Route myaleena.com/* already exists (id: $($apex.id))"
        exit 0
    }
} catch {
    Write-Host "Could not list routes: $_"
}

try {
    $r = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body $body
    if ($r.success) {
        Write-Host "Added route: myaleena.com/* -> $WorkerName"
    } else {
        Write-Error ($r.errors | ConvertTo-Json)
        exit 1
    }
} catch {
    Write-Error "Failed: $_"
    exit 1
}
