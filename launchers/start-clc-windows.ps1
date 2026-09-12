# Open the clc Cursor translator and the Claude Code TUI in two new windows.
# Does not attach to the caller's console (avoids dumping SSE into another TUI).
$ErrorActionPreference = 'Stop'
$Bin = Join-Path $env:USERPROFILE 'bin\clc.ps1'
if (-not (Test-Path $Bin)) {
    throw "missing $Bin - deploy launchers/clc.ps1 first"
}
$Title = 'clc Claude Code (Cursor)'
$cmd = "& { `$Host.UI.RawUI.WindowTitle = '$Title'; if (Test-Path Alias:clc) { Remove-Item Alias:clc -Force -ErrorAction SilentlyContinue }; Set-Location `$env:USERPROFILE; & '$($Bin.Replace("'","''"))' }"
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd
)
Write-Host "started $Title in a new window"
