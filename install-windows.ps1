# Install the visible-agent bridge (multi-agentic-harness) on Windows.
# Usage: powershell -ExecutionPolicy Bypass -File install-windows.ps1 [-ApiKey sk-...] [-BaseUrl http://127.0.0.1:8317]
#
# Deploys the bridge + cross-platform Claude worker runner to ~\.agent-bridge\,
# writes the CLIProxyAPI connection config, installs the captain-doctrine skill,
# and registers the MCP server with Claude Code (user scope).
param(
  [string]$ApiKey = "",
  [string]$BaseUrl = "http://127.0.0.1:8317"
)
$ErrorActionPreference = 'Stop'

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$BridgeDir = Join-Path $env:USERPROFILE '.agent-bridge'
New-Item -ItemType Directory -Force -Path $BridgeDir | Out-Null

# Python >=3.10 with the `mcp` package.
$Py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Py) { $Py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $Py) { throw 'Python not found on PATH. Install Python 3.10+ first.' }
& $Py -c "import mcp" 2>$null
if ($LASTEXITCODE -ne 0) { & $Py -m pip install --user mcp }

Copy-Item (Join-Path $Here 'visible_agent_bridge.py') $BridgeDir -Force
Copy-Item (Join-Path $Here 'claude_worker_runner.py') $BridgeDir -Force

if ($ApiKey -ne '') {
  $config = [ordered]@{ base_url = $BaseUrl; api_key = $ApiKey; claude_config_dir = '' } | ConvertTo-Json
  # BOM-less UTF-8 (PowerShell 5.1 Set-Content -Encoding UTF8 writes a BOM; the
  # bridge reads utf-8-sig so either works, but stay clean for other consumers).
  [System.IO.File]::WriteAllText((Join-Path $BridgeDir 'proxy.json'), $config, (New-Object System.Text.UTF8Encoding $false))
  Write-Host "Wrote $BridgeDir\proxy.json (base_url=$BaseUrl)"
} else {
  Write-Host 'NOTE: no -ApiKey supplied; workers will only run with use_proxy=False until proxy.json exists or CLIPROXY_API_KEY is set.'
}

# Captain doctrine skill for the manager session.
$SkillSrc = Join-Path $Here 'plugin\skills\claude-manages-codex'
if (Test-Path $SkillSrc) {
  $SkillDst = Join-Path $env:USERPROFILE '.claude\skills\claude-manages-codex'
  New-Item -ItemType Directory -Force -Path $SkillDst | Out-Null
  Copy-Item (Join-Path $SkillSrc '*') $SkillDst -Recurse -Force
  Write-Host 'Installed skill: claude-manages-codex'
}

# Register the MCP server with Claude Code (user scope; idempotent).
claude mcp remove agent-visibility -s user 2>$null | Out-Null
claude mcp add agent-visibility -s user -- $Py (Join-Path $BridgeDir 'visible_agent_bridge.py')
Write-Host "Registered MCP server 'agent-visibility' (user scope) using $Py"

& $Py -m py_compile (Join-Path $BridgeDir 'visible_agent_bridge.py') (Join-Path $BridgeDir 'claude_worker_runner.py')
Write-Host 'Install complete. Restart Claude Code, then check with the check_worker_backends MCP tool.'
