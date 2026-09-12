# Starts the clc Cursor Anthropic translator detached and hidden.
# Same pattern as start-gateway.ps1 for CLIProxyAPI / clx / clg.
# Invoked by the "CLCCursorGateway" scheduled task at logon.

$Py = (Get-Command py -ErrorAction SilentlyContinue)
if ($Py) { $PyExe = $Py.Source } else { $PyExe = "python" }
$Script = Join-Path $HOME ".agent-bridge\cursor_anthropic_gateway.py"
if (-not (Test-Path $Script)) {
    $Script = Join-Path $HOME "github-tools\multi-agentic-harness\gateway\cursor_anthropic_gateway.py"
}
$Log = Join-Path $HOME ".cc-bridge\clc-gateway-start.log"
$RunLog = Join-Path $HOME ".cc-bridge\clc-gateway-current.log"
$ErrLog = Join-Path $HOME ".cc-bridge\clc-gateway-current.err.log"
$KeyFile = Join-Path $HOME ".cc-bridge\secrets\cursor-api.key"

if (-not (Test-Path $Script)) { Write-Error "missing $Script"; exit 1 }

$LogDir = Split-Path $Log -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

Get-NetTCPConnection -LocalPort 8318 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    Add-Content -Path $Log -Value "stopping listener pid $($_.OwningProcess)" -Encoding utf8
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

Add-Content -Path $Log -Value "=== clc gateway start $(Get-Date -Format o) ===" -Encoding utf8

$env:CURSOR_API_KEY = if (Test-Path $KeyFile) { (Get-Content -Raw $KeyFile).Trim() } else { $env:CURSOR_API_KEY }
$env:CLC_WORKSPACE = $HOME

$proc = Start-Process -FilePath $PyExe `
    -ArgumentList @("-3", $Script, "--port", "8318", "--workspace", $HOME) `
    -WorkingDirectory $HOME `
    -WindowStyle Hidden `
    -RedirectStandardOutput $RunLog `
    -RedirectStandardError $ErrLog `
    -PassThru

Add-Content -Path $Log -Value "started detached, pid $($proc.Id)" -Encoding utf8

$ok = $false
foreach ($i in 1..40) {
    Start-Sleep -Seconds 1
    if (Get-NetTCPConnection -LocalPort 8318 -State Listen -ErrorAction SilentlyContinue) {
        $ok = $true
        break
    }
}

if ($ok) {
    Add-Content -Path $Log -Value "listening on 127.0.0.1:8318" -Encoding utf8
} else {
    Add-Content -Path $Log -Value "FAILED to bind 8318 - see $RunLog / $ErrLog" -Encoding utf8
    exit 1
}
