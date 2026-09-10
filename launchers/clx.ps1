# clx - Claude Code TUI on GROK models via the local CLIProxyAPI gateway.
#
# Picker facts (verified against the claude.exe binary in an earlier session):
#   CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY is DEAD for this kind of gateway -
#   it is guarded and filters ids to /^(claude|anthropic)/i, so it only fills the
#   picker with Claude aliases that 400 here. The tier slots accept ONLY real
#   Claude ids. Exactly ONE arbitrary model can enter the picker, via
#   ANTHROPIC_CUSTOM_MODEL_OPTION.

$Gateway = "http://127.0.0.1:8317"
$KeyFile = Join-Path $HOME ".cc-bridge\secrets\clx-api.key"

if (-not (Test-Path $KeyFile)) { Write-Error "clx: missing $KeyFile"; exit 1 }

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
$env:CLAUDE_CONFIG_DIR = Join-Path $HOME ".claude-clx"
$env:ANTHROPIC_BASE_URL = $Gateway
$env:ANTHROPIC_AUTH_TOKEN = $Key

$env:ANTHROPIC_MODEL = "grok-4.6(high)"
# The picker's Default row is structural; unset it derived a bogus
# "claude-grok-4.6(xhigh)" id, so point it at a real model.
$env:ANTHROPIC_DEFAULT_MODEL = "grok-4.6(high)"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION = "grok-4.6(high)"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_NAME = "Grok 4.6 high"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION = "xAI Grok 4.6 via CLIProxyAPI"
$env:ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES = "effort,xhigh_effort,thinking"

# NOTE: the tier slots are deliberately NOT set. Tested 2026-09-02: pointing
# ANTHROPIC_DEFAULT_OPUS_MODEL at a gateway-served Claude id does NOT take -
# `--model opus` still resolved to claude-opus-5 and 400'd. The broken aliases
# are removed from the picker via availableModels in settings.json instead.

$env:CLAUDE_CODE_MAX_CONTEXT_TOKENS = "500000"
$env:CLAUDE_CODE_AUTO_COMPACT_WINDOW = "500000"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"

# Effort: settings.json effortLevel did not apply to these non-Claude ids;
# the env var is authoritative for the session.
$env:CLAUDE_CODE_EFFORT_LEVEL = "high"
$env:CLAUDE_CODE_SUBAGENT_MODEL = "grok-4.6(high)"

if (-not (Test-Path $env:CLAUDE_CONFIG_DIR)) {
    New-Item -ItemType Directory -Path $env:CLAUDE_CONFIG_DIR | Out-Null
}

try {
    Invoke-RestMethod -Uri "$Gateway/v1/models" -TimeoutSec 3 `
        -Headers @{ "Authorization" = "Bearer $Key" } | Out-Null
} catch {
    Write-Error "clx: gateway not responding at $Gateway"
    Write-Host  "clx: start it with:  Start-ScheduledTask -TaskName CLIProxyAPI"
    Write-Host  "clx: (or run ~\cliproxyapi\start-gateway.ps1 directly)"
    exit 1
}

# Bypass permission prompts by default (owner request 2026-09-02).
# Prompting, not inference, was the dominant wall-clock cost: the same
# /read-past-sessions run took 10m59s while prompting and 1m54s with prompts
# off, vs 2m34s for the native Grok Build CLI on always-approve. Only 59s of
# that 11 minutes was API time. See ~\.cc-bridge\PERF-FINDINGS.md.
# An explicit permission flag on the command line still wins.
if (($args -join ' ') -match '--permission-mode|--dangerously-skip-permissions') {
    & claude @args
} else {
    & claude --dangerously-skip-permissions @args
}
