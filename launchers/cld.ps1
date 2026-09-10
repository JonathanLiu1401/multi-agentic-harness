# cld - Claude Code TUI on DEEPSEEK models via the local CLIProxyAPI gateway.
#
# Context window: DeepSeek models (deepseek-chat, deepseek-reasoner) support 64k tokens.
# Both CLAUDE_CODE_MAX_CONTEXT_TOKENS and CLAUDE_CODE_AUTO_COMPACT_WINDOW are pinned to 64000.

$Gateway = "http://127.0.0.1:8317"
$KeyFile = Join-Path $HOME ".cc-bridge\secrets\clx-api.key"

if (-not (Test-Path $KeyFile)) {
    Write-Error "cld: missing $KeyFile - please save your local client API key from config.yaml to $KeyFile"
    exit 1
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

$Key = (Get-Content -Raw $KeyFile).Trim()
$env:CLAUDE_CONFIG_DIR = Join-Path $HOME ".claude-cld"
$env:ANTHROPIC_BASE_URL = $Gateway
$env:ANTHROPIC_AUTH_TOKEN = $Key

$env:ANTHROPIC_MODEL = "deepseek-chat"
$env:ANTHROPIC_DEFAULT_MODEL = "deepseek-chat"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION = "deepseek-chat"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_NAME = "DeepSeek V3 (Chat)"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION = "DeepSeek V3 via CLIProxyAPI"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES = "thinking"

$env:CLAUDE_CODE_MAX_CONTEXT_TOKENS = "64000"
$env:CLAUDE_CODE_AUTO_COMPACT_WINDOW = "64000"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"

$env:CLAUDE_CODE_SUBAGENT_MODEL = "deepseek-chat"

if (-not (Test-Path $env:CLAUDE_CONFIG_DIR)) {
    New-Item -ItemType Directory -Path $env:CLAUDE_CONFIG_DIR | Out-Null
}

try {
    Invoke-RestMethod -Uri "$Gateway/v1/models" -TimeoutSec 3 `
        -Headers @{ "Authorization" = "Bearer $Key" } | Out-Null
} catch {
    Write-Error "cld: gateway not responding at $Gateway"
    Write-Host  "cld: start it with:  Start-ScheduledTask -TaskName CLIProxyAPI"
    Write-Host  "cld: (or run ~\cliproxyapi\start-gateway.ps1 directly)"
    exit 1
}

# Bypass permission prompts by default (matching clx/clg posture).
# An explicit permission flag on the command line still wins.
if (($args -join ' ') -match '--permission-mode|--dangerously-skip-permissions') {
    & claude @args
} else {
    & claude --dangerously-skip-permissions @args
}
