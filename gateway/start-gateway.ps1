# Starts the CLIProxyAPI gateway and appends its output to the log.
# Invoked by the "CLIProxyAPI" scheduled task at logon, and usable by hand.

$Root = Join-Path $HOME "cliproxyapi"
$Exe = Join-Path $Root "cli-proxy-api.exe"
$Cfg = Join-Path $Root "config.yaml"
$Log = Join-Path $HOME ".cc-bridge\gateway.log"

if (-not (Test-Path $Exe)) { Write-Error "missing $Exe"; exit 1 }
if (-not (Test-Path $Cfg)) { Write-Error "missing $Cfg"; exit 1 }

$LogDir = Split-Path $Log -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Roll the log if it has grown past 10 MB, keeping one previous copy.
if ((Test-Path $Log) -and ((Get-Item $Log).Length -gt 10MB)) {
    Move-Item -Path $Log -Destination "$Log.1" -Force
}

# Stop-ScheduledTask kills this wrapper but orphans the cli-proxy-api.exe child,
# which keeps port 8317 and makes the next start die with
# "bind: Only one usage of each socket address". Clear any survivor first.
Get-Process -Name "cli-proxy-api" -ErrorAction SilentlyContinue | ForEach-Object {
    Add-Content -Path $Log -Value "stopping orphaned gateway pid $($_.Id)" -Encoding utf8
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

Add-Content -Path $Log -Value "=== gateway start $(Get-Date -Format o) ===" -Encoding utf8

# Start DETACHED, not as a foreground child.
#
# Running it inline (`& $Exe ... | Out-File`) made the gateway share a console
# with this wrapper, so any Ctrl+C or console-close in that session killed it
# too - observed as scheduled-task lastResult 0xC000013A (STATUS_CONTROL_C_EXIT)
# with a clean, error-free log tail.
#
# Start-Process -RedirectStandardOutput cannot append, so it would truncate the
# log on every start; instead the child writes its own timestamped log and this
# wrapper exits immediately, leaving the gateway parented to the service host.
$RunLog = Join-Path $HOME ".cc-bridge\gateway-current.log"
$ErrLog = Join-Path $HOME ".cc-bridge\gateway-current.err.log"

$proc = Start-Process -FilePath $Exe `
    -ArgumentList @("--config", $Cfg) `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $RunLog `
    -RedirectStandardError $ErrLog `
    -PassThru

Add-Content -Path $Log -Value "started detached, pid $($proc.Id)" -Encoding utf8

# Confirm it actually bound the port before reporting success.
$ok = $false
foreach ($i in 1..20) {
    Start-Sleep -Seconds 1
    if (Get-NetTCPConnection -LocalPort 8317 -State Listen -ErrorAction SilentlyContinue) {
        $ok = $true
        break
    }
}

if ($ok) {
    Add-Content -Path $Log -Value "listening on 127.0.0.1:8317" -Encoding utf8
} else {
    Add-Content -Path $Log -Value "FAILED to bind 8317 - see $RunLog / $ErrLog" -Encoding utf8
    exit 1
}
