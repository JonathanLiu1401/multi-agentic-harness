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
    "CLAUDE_CODE_EFFORT_LEVEL",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS", "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
    "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SESSION_KIND",
    "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_CODE_BRIDGE_SESSION_ID",
    "ENABLE_TOOL_SEARCH")) {
    Remove-Item -Path "Env:$v" -ErrorAction SilentlyContinue
}

$env:CLAUDE_CONFIG_DIR = Join-Path $HOME ".claude-clo"
$env:ANTHROPIC_BASE_URL = $Endpoint
$env:ANTHROPIC_AUTH_TOKEN = $Key
# Empty string, not unset: Claude Code sends this as x-api-key. A leftover
# Anthropic key here bypasses OpenRouter entirely.
$env:ANTHROPIC_API_KEY = ""
$env:OPENROUTER_API_KEY = $Key

# Pin Union Alpha. cwd=$HOME makes ~/.claude/settings.json load as PROJECT
# settings and pin Opus 5. ANTHROPIC_MODEL overrides that (same as clx).
$env:ANTHROPIC_MODEL = "stealth/union-alpha[1m]"
$env:ANTHROPIC_DEFAULT_MODEL = "stealth/union-alpha[1m]"

$env:CLAUDE_CODE_MAX_CONTEXT_TOKENS = "1000000"
$env:CLAUDE_CODE_AUTO_COMPACT_WINDOW = "1000000"
$env:CLAUDE_CODE_MAX_OUTPUT_TOKENS = "8192"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
$env:CLAUDE_CODE_SKIP_FAST_MODE_ORG_CHECK = "1"
# Do NOT set ENABLE_TOOL_SEARCH. A custom ANTHROPIC_BASE_URL already
# disables optimistic tool-search ("not a first-party Anthropic host").
# auto / auto:N / true re-enables deferral and 400s Union Alpha / GPT.
$env:CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = "1"

if (-not (Test-Path $env:CLAUDE_CONFIG_DIR)) {
    New-Item -ItemType Directory -Path $env:CLAUDE_CONFIG_DIR | Out-Null
}

$homeResolved = (Resolve-Path $HOME).Path
$hereResolved = (Get-Location).Path
if ($hereResolved -eq $homeResolved) {
    $work = Join-Path $HOME ".claude-clo\workspace"
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    Set-Location $work
    Write-Host "clo: started from `$HOME; using $work so ~/.claude/settings.json cannot pin Opus"
}

# Rebuild /model from the live OpenRouter catalog (all modalities).
if (-not $env:CLO_SKIP_MODEL_REFRESH) {
    $Refresh = @(
        (Join-Path $HOME "github-tools\multi-agentic-harness\gateway\refresh_clo_models.py"),
        (Join-Path $HOME ".cc-bridge\refresh_clo_models.py")
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($Refresh) {
        try {
            $py = Get-Command py -ErrorAction SilentlyContinue
            if ($py) { & py -3 $Refresh } else { & python $Refresh }
        } catch {
            Write-Host "clo: catalog refresh failed; using previous picker"
        }
    }
}

# Bypass permission prompts by default (matching clx/clg/cld posture).
# An explicit permission flag on the command line still wins.
if (($args -join ' ') -match '--permission-mode|--dangerously-skip-permissions') {
    & claude @args
} else {
    & claude --dangerously-skip-permissions @args
}
