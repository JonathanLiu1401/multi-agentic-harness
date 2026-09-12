# Registers a per-user logon task that starts the clc Cursor translator.
# Mirrors cliproxyapi/install-autostart.ps1 (CLIProxyAPI for clx/clg).
#
#   powershell -ExecutionPolicy Bypass -File "$HOME\github-tools\multi-agentic-harness\gateway\install-clc-autostart.ps1"

$ErrorActionPreference = "Stop"

$TaskName = "CLCCursorGateway"
$Script = Join-Path $HOME "github-tools\multi-agentic-harness\gateway\start-clc-gateway.ps1"
$Deployed = Join-Path $HOME ".agent-bridge\start-clc-gateway.ps1"

if (-not (Test-Path $Script)) { Write-Error "missing $Script"; exit 1 }
New-Item -ItemType Directory -Force -Path (Join-Path $HOME ".agent-bridge") | Out-Null
Copy-Item $Script $Deployed -Force
Copy-Item (Join-Path $HOME "github-tools\multi-agentic-harness\gateway\cursor_anthropic_gateway.py") (Join-Path $HOME ".agent-bridge\cursor_anthropic_gateway.py") -Force

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing '$TaskName' task."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Get-NetTCPConnection -LocalPort 8318 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "Stopping listener pid $($_.OwningProcess)"
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Deployed`"" `
    -WorkingDirectory (Join-Path $HOME ".agent-bridge")

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Starts the local Cursor Anthropic translator on 127.0.0.1:8318 for the clc launcher." | Out-Null

Write-Host "Registered scheduled task '$TaskName' (at logon)."
Start-ScheduledTask -TaskName $TaskName
Write-Host "Started it now. Waiting for the port to come up..."

$ok = $false
foreach ($i in 1..40) {
    Start-Sleep -Seconds 1
    if (Get-NetTCPConnection -LocalPort 8318 -State Listen -ErrorAction SilentlyContinue) {
        $ok = $true
        break
    }
}

if ($ok) {
    Write-Host "clc gateway is up on 127.0.0.1:8318. Type clc in PowerShell."
} else {
    Write-Warning "Gateway did not answer within 40s. Check $HOME\.cc-bridge\clc-gateway-start.log"
}
