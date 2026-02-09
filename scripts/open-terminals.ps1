# Open Windows Terminal with 4 tabs in the AgenticContextBuilder root.
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$logPath = Join-Path $PSScriptRoot "terminal-launch.log"

function Invoke-CmdLine {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command
    )

    $proc = Start-Process -FilePath "cmd.exe" -ArgumentList @("/d", "/c", $Command) -Wait -PassThru -WindowStyle Hidden
    return $proc.ExitCode
}

try {
    "[$(Get-Date -Format o)] open-terminals.ps1" | Out-File -FilePath $logPath -Encoding utf8
    "repoRoot=$repoRoot" | Add-Content -Path $logPath

    $launchers = @("wt")
    $wtPath = Join-Path $env:LocalAppData "Microsoft\WindowsApps\wt.exe"
    if (Test-Path $wtPath) {
        $launchers += $wtPath
    }
    $pkgNames = @(
        "Microsoft.WindowsTerminal",
        "Microsoft.WindowsTerminalPreview",
        "Microsoft.WindowsTerminalDev"
    )
    foreach ($pkgName in $pkgNames) {
        $pkg = Get-AppxPackage -Name $pkgName -ErrorAction SilentlyContinue |
            Sort-Object Version -Descending |
            Select-Object -First 1
        if ($pkg) {
            $pkgWt = Join-Path $pkg.InstallLocation "wt.exe"
            if (Test-Path $pkgWt) {
                $launchers += $pkgWt
            }
        }
    }

    $completed = $false
    foreach ($launcher in $launchers) {
        "wtLauncher=$launcher" | Add-Content -Path $logPath
        $commands = @(
            ('start "" "{0}" -w new new-tab -d "{1}"' -f $launcher, $repoRoot),
            ('start "" "{0}" -w 0 new-tab -d "{1}"' -f $launcher, $repoRoot),
            ('start "" "{0}" -w 0 new-tab -d "{1}"' -f $launcher, $repoRoot),
            ('start "" "{0}" -w 0 new-tab -d "{1}"' -f $launcher, $repoRoot)
        )

        $launcherFailed = $false
        for ($i = 0; $i -lt $commands.Count; $i++) {
            $cmd = $commands[$i]
            "launcher=window0-step-$($i + 1)" | Add-Content -Path $logPath
            "cmd=$cmd" | Add-Content -Path $logPath
            $exitCode = Invoke-CmdLine -Command $cmd
            "exitCode=$exitCode" | Add-Content -Path $logPath
            if ($exitCode -ne 0) {
                $launcherFailed = $true
                break
            }
            if ($i -eq 0) {
                Start-Sleep -Milliseconds 2200
            }
            else {
                Start-Sleep -Milliseconds 1200
            }
        }
        if (-not $launcherFailed) {
            $completed = $true
            break
        }
    }    

    if (-not $completed) {
        throw "All launchers failed."
    }

    "status=ok" | Add-Content -Path $logPath
}
catch {
    "status=error" | Add-Content -Path $logPath
    $_ | Out-String | Add-Content -Path $logPath
    throw
}
