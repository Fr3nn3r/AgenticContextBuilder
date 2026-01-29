# Test VPN Connectivity
# Quick TCP port 443 connectivity test for internal Azure services

param(
    [string[]]$Hosts = @("10.1.0.5", "10.1.0.7"),
    [int]$Port = 443,
    [int]$TimeoutMs = 3000
)

function Test-TcpPort {
    param(
        [string]$IP,
        [int]$Port = 443,
        [int]$TimeoutMs = 3000
    )

    $client = New-Object Net.Sockets.TcpClient
    try {
        $asyncResult = $client.BeginConnect($IP, $Port, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            $client.Close()
            return [PSCustomObject]@{
                Host = $IP
                Port = $Port
                Status = "TIMEOUT"
                Color = "Yellow"
            }
        }
        $client.EndConnect($asyncResult)
        $client.Close()
        return [PSCustomObject]@{
            Host = $IP
            Port = $Port
            Status = "CONNECTED"
            Color = "Green"
        }
    }
    catch {
        $client.Close()
        return [PSCustomObject]@{
            Host = $IP
            Port = $Port
            Status = "ERROR"
            Color = "Red"
        }
    }
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "VPN Connectivity Test (Port $Port)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Known internal hosts
$knownHosts = @{
    "10.1.0.5" = "Azure OpenAI"
    "10.1.0.7" = "Azure Document Intelligence"
}

$allConnected = $true

foreach ($h in $Hosts) {
    $result = Test-TcpPort -IP $h -Port $Port -TimeoutMs $TimeoutMs
    $description = if ($knownHosts.ContainsKey($h)) { " ($($knownHosts[$h]))" } else { "" }

    Write-Host "  $($result.Host):$($result.Port)$description - " -NoNewline
    Write-Host $result.Status -ForegroundColor $result.Color

    if ($result.Status -ne "CONNECTED") {
        $allConnected = $false
    }
}

Write-Host ""
if ($allConnected) {
    Write-Host "VPN connection is active - all hosts reachable." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some hosts unreachable - check VPN connection." -ForegroundColor Yellow
    exit 1
}
