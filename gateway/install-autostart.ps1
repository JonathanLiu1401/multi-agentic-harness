# Registers a per-user scheduled task that starts the CLIProxyAPI gateway at
# logon, so `clx` works after a reboot without starting anything by hand.
#
# Run this yourself:   ! powershell -ExecutionPolicy Bypass -File "$HOME\cliproxyapi\install-autostart.ps1"
#
# No elevation needed: it is a per-user logon task, not a system service.
# To undo:  Unregister-ScheduledTask -TaskName CLIProxyAPI -Confirm:$false

$ErrorActionPreference = "Stop"

$TaskName = "CLIProxyAPI"
$Script = Join-Path $HOME "cliproxyapi\start-gateway.ps1"

if (-not (Test-Path $Script)) { Write-Error "missing $Script"; exit 1 }

# Remove any previous registration so this script is safe to re-run.
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing '$TaskName' task."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Stop anything already listening, so the task owns port 8317 cleanly.
Get-Process -Name "cli-proxy-api" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "Stopping running gateway (pid $($_.Id))."
    Stop-Process -Id $_.Id -Force
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Script`"" `
    -WorkingDirectory (Join-Path $HOME "cliproxyapi")

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
    -Description "Starts the local CLIProxyAPI gateway on 127.0.0.1:8317 for the clx launcher." | Out-Null

Write-Host "Registered scheduled task '$TaskName' (at logon)."

Start-ScheduledTask -TaskName $TaskName
Write-Host "Started it now. Waiting for the port to come up..."

$key = (Get-Content -Raw (Join-Path $HOME ".cc-bridge\secrets\clx-api.key")).Trim()
$ok = $false
foreach ($i in 1..20) {
    Start-Sleep -Seconds 1
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:8317/v1/models" -TimeoutSec 3 `
            -Headers @{ "Authorization" = "Bearer $key" } | Out-Null
        $ok = $true
        break
    } catch { }
}

if ($ok) {
    Write-Host "Gateway is up on 127.0.0.1:8317. clx is ready."
} else {
    Write-Warning "Gateway did not answer within 20s. Check $HOME\.cc-bridge\gateway.log"
}
