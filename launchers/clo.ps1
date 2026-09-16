# clo - Claude Code TUI on OpenRouter models (direct Anthropic skin).
#
# Official integration (2026): ANTHROPIC_BASE_URL=https://openrouter.ai/api
# with NO /v1. /v1 is the OpenAI skin and 404s Claude Code's /v1/messages.
# ANTHROPIC_API_KEY must be the empty string so Claude Code does not send a
# real x-api-key and skip the gateway. Auth is ANTHROPIC_AUTH_TOKEN.
# Docs: https://openrouter.ai/docs/guides/coding-agents/claude-code-integration
#
# Context window: 1M process-wide. CLAUDE_CODE_EFFORT_LEVEL is omitted so
# /effort and the status-bar slider can change reasoning effort.

$Endpoint = "https://openrouter.ai/api"
$KeyFile = Join-Path $HOME ".cc-bridge\secrets\openrouter-api.key"

if (-not (Test-Path $KeyFile)) {
    if ($env:OPENROUTER_API_KEY) {
        $Key = $env:OPENROUTER_API_KEY
    } else {
        Write-Error "clo: missing $KeyFile and OPENROUTER_API_KEY env var - save your sk-or- key to $KeyFile"
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
    "CLAUDE_CODE_EFFORT_LEVEL", "CLAUDE_CODE_MAX_OUTPUT_TOKENS")) {
    Remove-Item -Path "Env:$v" -ErrorAction SilentlyContinue
}

$env:CLAUDE_CONFIG_DIR = Join-Path $HOME ".claude-clo"
$env:ANTHROPIC_BASE_URL = $Endpoint
$env:ANTHROPIC_AUTH_TOKEN = $Key
# Empty string, not unset: Claude Code sends this as x-api-key. A leftover
# Anthropic key here bypasses OpenRouter entirely.
$env:ANTHROPIC_API_KEY = ""
$env:OPENROUTER_API_KEY = $Key

$env:ANTHROPIC_MODEL = "~anthropic/claude-sonnet-latest[1m]"
$env:ANTHROPIC_DEFAULT_MODEL = "~anthropic/claude-sonnet-latest[1m]"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION = "~anthropic/claude-sonnet-latest[1m]"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_NAME = "Claude Sonnet latest"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION = "Anthropic Sonnet latest via OpenRouter (1M ctx)"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES = "effort,max_effort,thinking"

$env:CLAUDE_CODE_MAX_CONTEXT_TOKENS = "1000000"
$env:CLAUDE_CODE_AUTO_COMPACT_WINDOW = "1000000"
$env:CLAUDE_CODE_MAX_OUTPUT_TOKENS = "8192"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
$env:CLAUDE_CODE_SKIP_FAST_MODE_ORG_CHECK = "1"
$env:CLAUDE_CODE_SUBAGENT_MODEL = "~anthropic/claude-sonnet-latest[1m]"
# Deferred/tool-search custom tools 400 on non-Anthropic OpenRouter slugs
# ("Deferred custom tools are only supported on Anthropic models").
$env:ENABLE_TOOL_SEARCH = "false"

if (-not (Test-Path $env:CLAUDE_CONFIG_DIR)) {
    New-Item -ItemType Directory -Path $env:CLAUDE_CONFIG_DIR | Out-Null
}

# Bypass permission prompts by default (matching clx/clg/cld posture).
# An explicit permission flag on the command line still wins.
if (($args -join ' ') -match '--permission-mode|--dangerously-skip-permissions') {
    & claude @args
} else {
    & claude --dangerously-skip-permissions @args
}
