# clc - Claude Code TUI on CURSOR models via the local Anthropic translator.
#
# Same shape as clx/clg: isolated CLAUDE_CONFIG_DIR + ANTHROPIC_BASE_URL.
# The translator is a hidden logon task (CLCCursorGateway), like CLIProxyAPI
# for clx/clg. This script does not open extra windows.

$Gateway = "http://127.0.0.1:8318"
$KeyFile = Join-Path $HOME ".cc-bridge\secrets\cursor-api.key"

if (-not (Test-Path $KeyFile)) {
    if (-not $env:CURSOR_API_KEY) {
        Write-Error "clc: missing $KeyFile and CURSOR_API_KEY - save your crsr_ key to $KeyFile"
        exit 1
    }
} else {
    $env:CURSOR_API_KEY = (Get-Content -Raw $KeyFile).Trim()
}

foreach ($v in @(
    "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_DEFAULT_FABLE_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL", "ANTHROPIC_CUSTOM_MODEL_OPTION",
    "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE",
    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY")) {
    Remove-Item -Path "Env:$v" -ErrorAction SilentlyContinue
}

$env:CLAUDE_CONFIG_DIR = Join-Path $HOME ".claude-clc"
$env:ANTHROPIC_BASE_URL = $Gateway
$env:ANTHROPIC_AUTH_TOKEN = "clc"
$env:CLC_WORKSPACE = (Get-Location).Path

$env:ANTHROPIC_MODEL = "grok-4.6-fast"
$env:ANTHROPIC_DEFAULT_MODEL = "grok-4.6-fast"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION = "grok-4.6-fast"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_NAME = "Cursor Grok 4.6 Fast"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION = "Cursor Grok 4.6 fast via clc translator"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES = "effort,thinking"

# Process-wide. Claude Code cannot set this per /model. Most Cursor-hosted
# models are 1m; grok-4.6 is 500k natively but /context will still show 1m.
$env:CLAUDE_CODE_MAX_CONTEXT_TOKENS = "1000000"
$env:CLAUDE_CODE_AUTO_COMPACT_WINDOW = "1000000"
# Do not set CLAUDE_CODE_EFFORT_LEVEL. That env blocks /effort in the TUI
# and forced every Cursor model to high (dashboard gemini-3.8-flash-high
# when the user had saved low). The gateway reads effort from the request
# body and from ~/.claude-clc/settings.json effortLevel.
Remove-Item -Path Env:CLAUDE_CODE_EFFORT_LEVEL -ErrorAction SilentlyContinue
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
$env:CLAUDE_CODE_SUBAGENT_MODEL = "grok-4.6-fast"

if (-not (Test-Path $env:CLAUDE_CONFIG_DIR)) {
    New-Item -ItemType Directory -Path $env:CLAUDE_CONFIG_DIR | Out-Null
}

try {
    Invoke-RestMethod -Uri "$Gateway/health" -TimeoutSec 3 | Out-Null
} catch {
    Write-Error "clc: gateway not responding at $Gateway"
    Write-Host  "clc: start it with:  Start-ScheduledTask -TaskName CLCCursorGateway"
    Write-Host  "clc: (or run ~\github-tools\multi-agentic-harness\gateway\start-clc-gateway.ps1)"
    exit 1
}

if (($args -join " ") -match "--permission-mode|--dangerously-skip-permissions") {
    & claude @args
} else {
    & claude --dangerously-skip-permissions @args
}
