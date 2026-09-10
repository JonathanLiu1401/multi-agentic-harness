# Stops the CLIProxyAPI gateway properly.
#
# Stop-ScheduledTask on its own is NOT enough: it kills the task's PowerShell
# wrapper but leaves cli-proxy-api.exe running and holding port 8317, so the
# next start fails with "bind: Only one usage of each socket address".
#
# Run:  powershell -ExecutionPolicy Bypass -File "$HOME\cliproxyapi\stop-gateway.ps1"

$task = Get-ScheduledTask -TaskName CLIProxyAPI -ErrorAction SilentlyContinue
if ($task -and $task.State -eq "Running") {
    Stop-ScheduledTask -TaskName CLIProxyAPI
    Write-Host "Stopped scheduled task."
}

$procs = Get-Process -Name "cli-proxy-api" -ErrorAction SilentlyContinue
if ($procs) {
    $procs | ForEach-Object {
        Write-Host "Stopping gateway process pid $($_.Id)."
        Stop-Process -Id $_.Id -Force
    }
} else {
    Write-Host "No gateway process running."
}

Start-Sleep -Seconds 2
$still = Get-NetTCPConnection -LocalPort 8317 -State Listen -ErrorAction SilentlyContinue
if ($still) {
    Write-Warning ("Port 8317 still held by pid {0}." -f $still[0].OwningProcess)
} else {
    Write-Host "Port 8317 is free."
}
