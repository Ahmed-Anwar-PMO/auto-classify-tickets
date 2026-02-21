# Test Zendesk image webhook - forces TLS 1.2 to avoid "connection was closed"
# Use -Direct to hit Render and get predictions in response (Worker returns 200 immediately, no results)
param(
    [int]$TicketId = 303847,
    [string]$Secret = "22081994",
    [switch]$Direct  # Hit Render directly to get predictions in response
)

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$json = "{`"ticket_id`": $TicketId}"
$headers = @{
    "Content-Type"     = "application/json"
    "x-webhook-secret" = $Secret
}

$uri = if ($Direct) {
    "https://image-matcher-whm0.onrender.com/webhook/zendesk"
} else {
    "https://myaleena.com/webhook/zendesk"
}

try {
    $r = Invoke-RestMethod -Uri $uri -Method POST -ContentType "application/json" -Headers $headers -Body $json -TimeoutSec 120
    $r | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
