# cld - Claude Code TUI on DeepSeek models (DeepSeek V4.1 Flash & V4 Pro, 1M context).
#
# Direct Anthropic compatibility via https://api.deepseek.com/anthropic.
# Context window: 1M context (1000000 tokens) for all models.
# Dynamic effort: CLAUDE_CODE_EFFORT_LEVEL is intentionally omitted so /effort
# and the status bar effort slider can dynamically change reasoning effort.

$Endpoint = "https://api.deepseek.com/anthropic"
$KeyFile = Join-Path $HOME ".cc-bridge\secrets\deepseek-api.key"

if (-not (Test-Path $KeyFile)) {
    if ($env:DEEPSEEK_API_KEY) {
        $Key = $env:DEEPSEEK_API_KEY
    } else {
        Write-Error "cld: missing $KeyFile and DEEPSEEK_API_KEY env var - please save your DeepSeek API key to $KeyFile"
        exit 1
    }
} else {
    $Key = (Get-Content -Raw $KeyFile).Trim()
}

foreach ($v in @(
    "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_DEFAULT_FABLE_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL", "ANTHROPIC_CUSTOM_MODEL_OPTION",
    "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE",
    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY",
    "CLAUDE_CODE_EFFORT_LEVEL")) {
    Remove-Item -Path "Env:$v" -ErrorAction SilentlyContinue
}

$env:CLAUDE_CONFIG_DIR = Join-Path $HOME ".claude-cld"
$env:ANTHROPIC_BASE_URL = $Endpoint
$env:ANTHROPIC_AUTH_TOKEN = $Key

$env:ANTHROPIC_MODEL = "deepseek-flash[1m]"
$env:ANTHROPIC_DEFAULT_MODEL = "deepseek-flash[1m]"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = "deepseek-v4-pro[1m]"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "deepseek-flash[1m]"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = "deepseek-flash"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION = "deepseek-flash[1m]"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_NAME = "DeepSeek V4.1 Flash"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION = "DeepSeek V4.1 Flash (1M context)"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES = "effort,max_effort,thinking"

$env:CLAUDE_CODE_MAX_CONTEXT_TOKENS = "1000000"
$env:CLAUDE_CODE_AUTO_COMPACT_WINDOW = "1000000"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"

$env:CLAUDE_CODE_SUBAGENT_MODEL = "deepseek-flash[1m]"

if (-not (Test-Path $env:CLAUDE_CONFIG_DIR)) {
    New-Item -ItemType Directory -Path $env:CLAUDE_CONFIG_DIR | Out-Null
}

# Bypass permission prompts by default (matching clx/clg posture).
# An explicit permission flag on the command line still wins.
if (($args -join ' ') -match '--permission-mode|--dangerously-skip-permissions') {
    & claude @args
} else {
    & claude --dangerously-skip-permissions @args
}
