# Test Azure Credentials
# Tests Azure OpenAI and Azure Document Intelligence connectivity

param(
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "Azure Credentials Test" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan

# Load .env file
$envFile = Join-Path $PSScriptRoot "..\.env"
if (Test-Path $envFile) {
    Write-Host "`nLoading .env from: $envFile"
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
} else {
    Write-Host ".env file not found at $envFile" -ForegroundColor Red
    exit 1
}

Write-Host ("-" * 60)

# ============================================================================
# Test 1: Azure OpenAI
# ============================================================================
Write-Host "`n[1] Testing Azure OpenAI..." -ForegroundColor Yellow
Write-Host ("-" * 40)

$aoaiKey = $env:AZURE_OPENAI_API_KEY
$aoaiEndpoint = $env:AZURE_OPENAI_BASE_URL
$aoaiDeployment = if ($env:AZURE_OPENAI_DEPLOYMENT) { $env:AZURE_OPENAI_DEPLOYMENT } else { "gpt-4o" }
$aoaiVersion = if ($env:AZURE_OPENAI_API_VERSION) { $env:AZURE_OPENAI_API_VERSION } else { "2024-02-15-preview" }

# Clean up endpoint - remove /openai/v1/ suffix if present
if ($aoaiEndpoint) {
    $aoaiEndpoint = $aoaiEndpoint.TrimEnd('/')
    if ($aoaiEndpoint.EndsWith("/openai/v1")) {
        $aoaiEndpoint = $aoaiEndpoint.Substring(0, $aoaiEndpoint.Length - "/openai/v1".Length)
    }
}

$maskedKey = if ($aoaiKey) { "********" + $aoaiKey.Substring($aoaiKey.Length - 4) } else { "NOT SET" }
Write-Host "  Endpoint:   $aoaiEndpoint"
Write-Host "  API Key:    $maskedKey"
Write-Host "  Deployment: $aoaiDeployment"
Write-Host "  Version:    $aoaiVersion"

$aoaiResult = $false
if ($aoaiKey -and $aoaiEndpoint) {
    try {
        $uri = "$aoaiEndpoint/openai/deployments/$aoaiDeployment/chat/completions?api-version=$aoaiVersion"
        $body = @{
            messages = @(
                @{ role = "user"; content = "Say 'Hello' and nothing else." }
            )
            max_tokens = 10
            temperature = 0
        } | ConvertTo-Json -Depth 3

        Write-Host "`n  Making test request..."
        $response = Invoke-RestMethod -Uri $uri -Method Post -Headers @{
            "api-key" = $aoaiKey
            "Content-Type" = "application/json"
        } -Body $body

        $reply = $response.choices[0].message.content
        $model = $response.model
        $promptTokens = $response.usage.prompt_tokens
        $completionTokens = $response.usage.completion_tokens

        Write-Host "  Response: $reply" -ForegroundColor Green
        Write-Host "  Model: $model"
        Write-Host "  Tokens: $promptTokens prompt + $completionTokens completion"
        Write-Host "`n  SUCCESS: Azure OpenAI is working!" -ForegroundColor Green
        $aoaiResult = $true
    }
    catch {
        Write-Host "`n  FAILED: $($_.Exception.Message)" -ForegroundColor Red
    }
} else {
    Write-Host "`n  SKIP: Missing Azure OpenAI credentials" -ForegroundColor Yellow
}

# ============================================================================
# Test 2: Azure Document Intelligence
# ============================================================================
Write-Host "`n[2] Testing Azure Document Intelligence..." -ForegroundColor Yellow
Write-Host ("-" * 40)

$diKey = $env:AZURE_DI_API_KEY
$diEndpoint = $env:AZURE_DI_ENDPOINT

$maskedDiKey = if ($diKey) { "********" + $diKey.Substring($diKey.Length - 4) } else { "NOT SET" }
Write-Host "  Endpoint: $diEndpoint"
Write-Host "  API Key:  $maskedDiKey"

$diResult = $false
if ($diKey -and $diEndpoint) {
    try {
        $uri = "$($diEndpoint.TrimEnd('/'))/documentintelligence/documentModels?api-version=2024-11-30"

        Write-Host "`n  Listing available models..."
        $response = Invoke-RestMethod -Uri $uri -Method Get -Headers @{
            "Ocp-Apim-Subscription-Key" = $diKey
        }

        $models = $response.value
        Write-Host "  Found $($models.Count) models available:" -ForegroundColor Green
        $models | Select-Object -First 5 | ForEach-Object {
            Write-Host "    - $($_.modelId)"
        }
        if ($models.Count -gt 5) {
            Write-Host "    ... and $($models.Count - 5) more"
        }
        Write-Host "`n  SUCCESS: Azure Document Intelligence is working!" -ForegroundColor Green
        $diResult = $true
    }
    catch {
        $errorMsg = $_.Exception.Message
        if ($errorMsg -match "403|Firewall|Virtual Network") {
            Write-Host "`n  FAILED: Access denied - VPN connection required" -ForegroundColor Red
        } else {
            Write-Host "`n  FAILED: $errorMsg" -ForegroundColor Red
        }
    }
} else {
    Write-Host "`n  SKIP: Missing Azure DI credentials" -ForegroundColor Yellow
}

# ============================================================================
# Summary
# ============================================================================
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan

$aoaiStatus = if ($aoaiResult) { "PASS" } else { "FAIL/SKIP" }
$diStatus = if ($diResult) { "PASS" } else { "FAIL/SKIP" }

$aoaiColor = if ($aoaiResult) { "Green" } else { "Red" }
$diColor = if ($diResult) { "Green" } else { "Red" }

Write-Host "  Azure OpenAI:                " -NoNewline
Write-Host $aoaiStatus -ForegroundColor $aoaiColor

Write-Host "  Azure Document Intelligence: " -NoNewline
Write-Host $diStatus -ForegroundColor $diColor

if ($aoaiResult -and $diResult) {
    Write-Host "`nAll tests passed!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`nSome tests failed or were skipped." -ForegroundColor Yellow
    exit 1
}
