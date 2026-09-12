# Install the Multi-Agentic Harness on Windows.
# Usage: powershell -ExecutionPolicy Bypass -File install-windows.ps1
#
# This script installs both parts of the Multi-Agentic Harness:
#   Part 1: The Multi-Agent Worker Bridge (Claude manages Cursor, Grok, Agy, and headless workers)
#   Part 2: Provider Profiles & Launchers (clx, clg, cld, clc for Grok, Gemini, DeepSeek, and Cursor)
$ErrorActionPreference = 'Stop'

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$UserHome = $env:USERPROFILE

Write-Host "============================================================"
Write-Host "Installing Multi-Agentic Harness"
Write-Host "============================================================"

# ---------------------------------------------------------------------------
# Prerequisites Check
# ---------------------------------------------------------------------------
$Py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Py) { $Py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $Py) { throw "Python not found on PATH. Please install Python 3.10+ first." }
Write-Host "Using Python: $Py"

# Check for FastMCP or MCPServer capability (supports both mcp 1.x and mcp 2.x+)
$mcpCheckCode = @'
import sys
try:
    from mcp.server.fastmcp import FastMCP
    sys.exit(0)
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.mcpserver import MCPServer
        sys.exit(0)
    except (ImportError, ModuleNotFoundError):
        try:
            from fastmcp import FastMCP
            sys.exit(0)
        except (ImportError, ModuleNotFoundError):
            sys.exit(1)
'@

$prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'SilentlyContinue'
$mcpCheckCode | & $Py - *>$null
$mcpCheckExit = $LASTEXITCODE
if ($mcpCheckExit -ne 0) {
    Write-Host "Installing python mcp package..."
    & $Py -m pip install --user mcp
    $mcpCheckCode | & $Py - *>$null
    if ($LASTEXITCODE -ne 0) {
        & $Py -m pip install --user fastmcp
    }
}
$ErrorActionPreference = $prevEAP

# ---------------------------------------------------------------------------
# PART 1: Multi-Agent Worker Bridge (claude-manages-xxx)
# ---------------------------------------------------------------------------
Write-Host "`n--- Part 1: Multi-Agent Worker Bridge ---"

# 1. Deploy bridge scripts to ~/.agent-bridge/
$BridgeDir = Join-Path $UserHome ".agent-bridge"
New-Item -ItemType Directory -Force -Path $BridgeDir | Out-Null

@('visible_agent_bridge.py', 'claude_worker_runner.py', 'cursor_worker_runner.py', 'captain_checkup.py', 'cursor_cloud_api.py', 'gateway\cursor_anthropic_gateway.py') | ForEach-Object {
    $src = Join-Path $Here $_
    if (Test-Path $src) {
        Copy-Item $src $BridgeDir -Force
    }
}
Write-Host "Deployed bridge runners to $BridgeDir"

# Compile python files to verify syntax
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'SilentlyContinue'
& $Py -m py_compile (Join-Path $BridgeDir 'visible_agent_bridge.py') (Join-Path $BridgeDir 'claude_worker_runner.py') (Join-Path $BridgeDir 'cursor_worker_runner.py') (Join-Path $BridgeDir 'captain_checkup.py') (Join-Path $BridgeDir 'cursor_cloud_api.py') (Join-Path $BridgeDir 'cursor_anthropic_gateway.py')
if ($LASTEXITCODE -eq 0) {
    Write-Host "Python bridge syntax validated successfully."
}
$ErrorActionPreference = $prevEAP

# 2. Deploy captain doctrine skill: claude-manages-codex
$SkillSrc = Join-Path $Here 'plugin\skills\claude-manages-codex'
if (Test-Path $SkillSrc) {
    $SkillDst = Join-Path $UserHome '.claude\skills\claude-manages-codex'
    New-Item -ItemType Directory -Force -Path $SkillDst | Out-Null
    Copy-Item (Join-Path $SkillSrc '*') $SkillDst -Recurse -Force
    Write-Host "Installed skill: claude-manages-codex"
}

# 3. Register MCP server with Claude Code (user scope; idempotent)
# In PowerShell 5.1, native executables writing to stderr throw terminating errors
# if ErrorActionPreference is 'Stop'. Temporarily switch to SilentlyContinue.
$ClaudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if ($ClaudeCmd) {
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        & claude mcp remove agent-visibility -s user *>$null
    } catch { }
    try {
        & claude mcp add agent-visibility -s user -- $Py (Join-Path $BridgeDir 'visible_agent_bridge.py') *>$null
        Write-Host "Registered MCP server 'agent-visibility' (user scope)"
    } catch {
        Write-Warning "Failed to register MCP server 'agent-visibility': $_"
    } finally {
        $ErrorActionPreference = $prevEAP
    }
} else {
    Write-Warning "claude CLI not found on PATH. Please install Claude Code first."
}

# 4. Deploy cursor-agent Git Bash shim to ~/.local/bin/
$LocalBin = Join-Path $UserHome '.local\bin'
New-Item -ItemType Directory -Force -Path $LocalBin | Out-Null
$ShimSrc = Join-Path $Here 'shims\cursor-agent'
if (Test-Path $ShimSrc) {
    $ShimDst = Join-Path $LocalBin 'cursor-agent'
    $text = [System.IO.File]::ReadAllText($ShimSrc) -replace "`r`n", "`n" -replace "`r", "`n"
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($ShimDst, $text, $utf8)
    Write-Host "Installed cursor-agent Git Bash shim: $ShimDst"
}

# ---------------------------------------------------------------------------
# PART 2: Provider Profiles, Launchers & Gateway (clx, clg, cld)
# ---------------------------------------------------------------------------
Write-Host "`n--- Part 2: Provider Profiles & Launchers (clx, clg, cld) ---"

# 1. Deploy native subagent definitions to ~/.claude/agents/
$AgentsSrc = Join-Path $Here 'plugin\agents'
if (Test-Path $AgentsSrc) {
    $AgentsDst = Join-Path $UserHome '.claude\agents'
    New-Item -ItemType Directory -Force -Path $AgentsDst | Out-Null
    Copy-Item (Join-Path $AgentsSrc '*.md') $AgentsDst -Force
    Write-Host "Installed subagent definitions: grok, agy-gemini-3-8-flash, deepseek"
}

# 2. Deploy launchers to ~/bin/ and ~/.local/bin/
$LaunchersSrc = Join-Path $Here 'launchers'
if (Test-Path $LaunchersSrc) {
    $BinDst = Join-Path $UserHome 'bin'
    New-Item -ItemType Directory -Force -Path $BinDst | Out-Null

    # Shell scripts and PowerShell scripts to ~/bin
    @('clx', 'clg', 'cld', 'clc', 'clx.ps1', 'clg.ps1', 'cld.ps1', 'clc.ps1') | ForEach-Object {
        $f = Join-Path $LaunchersSrc $_
        if (Test-Path $f) {
            Copy-Item $f (Join-Path $BinDst $_) -Force
        }
    }
    # Windows CMD shims to ~/.local/bin
    @('clx.cmd', 'clg.cmd', 'cld.cmd', 'clc.cmd') | ForEach-Object {
        $f = Join-Path $LaunchersSrc $_
        if (Test-Path $f) {
            Copy-Item $f (Join-Path $LocalBin $_) -Force
        }
    }
    Write-Host "Installed launchers (clx, clg, cld, clc) to $BinDst and $LocalBin"
}

# 3. Ensure ~/.local/bin is in Windows User Path
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$LocalBin*") {
    $NewUserPath = "$LocalBin;$UserPath"
    [Environment]::SetEnvironmentVariable("Path", $NewUserPath, "User")
    $env:Path = "$LocalBin;$env:Path"
    Write-Host "Added $LocalBin to User PATH environment variable."
} else {
    Write-Host "$LocalBin is already on User PATH."
}

# 4. Deploy profile templates and create junctions for shared agents & skills
$Profiles = @(
    @{ Name = "claude-clx"; Provider = "Grok" },
    @{ Name = "claude-clg"; Provider = "Gemini/Antigravity" },
    @{ Name = "claude-cld"; Provider = "DeepSeek" },
    @{ Name = "claude-clc"; Provider = "Cursor" }
)

foreach ($p in $Profiles) {
    $pDir = Join-Path $UserHome (".$($p.Name)")
    New-Item -ItemType Directory -Force -Path $pDir | Out-Null

    $tplDir = Join-Path $Here "templates\$($p.Name)"
    if (Test-Path $tplDir) {
        Copy-Item (Join-Path $tplDir "settings.json") (Join-Path $pDir "settings.json") -Force
        Copy-Item (Join-Path $tplDir "CLAUDE.md") (Join-Path $pDir "CLAUDE.md") -Force
    }

    # Link agents and skills junctions
    $agentsJunction = Join-Path $pDir "agents"
    if (-not (Test-Path $agentsJunction)) {
        New-Item -ItemType Junction -Path $agentsJunction -Target (Join-Path $UserHome ".claude\agents") | Out-Null
    }
    $skillsJunction = Join-Path $pDir "skills"
    if (-not (Test-Path $skillsJunction)) {
        New-Item -ItemType Junction -Path $skillsJunction -Target (Join-Path $UserHome ".claude\skills") | Out-Null
    }
    Write-Host "Configured profile: .$($p.Name) ($($p.Provider))"
}

# 5. Initialize Secrets Directory and Gateway Scripts
$SecretsDir = Join-Path $UserHome ".cc-bridge\secrets"
New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null

$ClxKeyFile = Join-Path $SecretsDir "clx-api.key"
if (-not (Test-Path $ClxKeyFile)) {
    # Generate a random 24-byte hex key for local CLIProxyAPI authentication
    $bytes = New-Object byte[] 24
    (New-Object System.Security.Cryptography.RNGCryptoServiceProvider).GetBytes($bytes)
    $hex = -join ($bytes | ForEach-Object { "{0:x2}" -f $_ })
    $localKey = "ccp-$hex"
    [System.IO.File]::WriteAllText($ClxKeyFile, $localKey, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "Generated local gateway client key: $ClxKeyFile"
}

$CursorKeyFile = Join-Path $SecretsDir "cursor-api.key"
if (-not (Test-Path $CursorKeyFile)) {
    Write-Host "clc: no $CursorKeyFile yet. Save your crsr_ key there (Cursor Dashboard -> API keys)."
}

# PowerShell ships `clc` as a ReadOnly AllScope alias for Clear-Content.
# Without this, typing `clc` in PowerShell never reaches clc.cmd.
$ClcMarker = "# clc launcher (Cursor Claude Code dialect) - shadows PowerShell Clear-Content alias"
$ClcSnippet = @"
$ClcMarker
if (Test-Path Alias:clc) { Remove-Item Alias:clc -Force -ErrorAction SilentlyContinue }
function global:clc { & "`$env:USERPROFILE\bin\clc.ps1" @args }
"@
$ProfileCandidates = @(
    (Join-Path $UserHome "Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1"),
    (Join-Path $UserHome "Documents\PowerShell\Microsoft.PowerShell_profile.ps1")
)
foreach ($prof in $ProfileCandidates) {
    $profDir = Split-Path $prof -Parent
    if (-not (Test-Path $profDir)) {
        New-Item -ItemType Directory -Force -Path $profDir | Out-Null
    }
    $existing = ""
    if (Test-Path $prof) {
        $existing = Get-Content -Raw $prof
    }
    if ($existing -notlike "*$ClcMarker*") {
        $utf8 = New-Object System.Text.UTF8Encoding $false
        if ($existing -and -not $existing.EndsWith("`n")) { $existing = $existing + "`r`n" }
        [System.IO.File]::WriteAllText($prof, $existing + $ClcSnippet + "`r`n", $utf8)
        Write-Host "Patched PowerShell profile for clc alias: $prof"
    }
}

$GatewayDir = Join-Path $UserHome "cliproxyapi"
New-Item -ItemType Directory -Force -Path $GatewayDir | Out-Null
$GatewaySrc = Join-Path $Here "gateway"
if (Test-Path $GatewaySrc) {
    Copy-Item (Join-Path $GatewaySrc "*.ps1") $GatewayDir -Force
    if (-not (Test-Path (Join-Path $GatewayDir "config.yaml"))) {
        $cfgTemplate = Join-Path $GatewaySrc "config.example.yaml"
        if (Test-Path $cfgTemplate) {
            $keyContent = (Get-Content -Raw $ClxKeyFile).Trim()
            $cfg = Get-Content -Raw $cfgTemplate
            $cfg = $cfg -replace "ccp-your-local-client-api-key-here", $keyContent
            [System.IO.File]::WriteAllText((Join-Path $GatewayDir "config.yaml"), $cfg, (New-Object System.Text.UTF8Encoding $false))
            Write-Host "Created initial gateway config at $GatewayDir\config.yaml"
        }
    }
    Write-Host "Deployed gateway management scripts to $GatewayDir"
}

# Cursor translator (clc): hidden logon task on 127.0.0.1:8318
$ClcAutostart = Join-Path $Here "gateway\install-clc-autostart.ps1"
if (Test-Path $ClcAutostart) {
    Write-Host "Installing CLCCursorGateway scheduled task..."
    & $ClcAutostart
}

# 6. Inject accurate model pricing into .claude.json state caches
# Uses Python to safely parse, back up, and update JSON without data loss.
$PricingPyScript = @'
import json, os, shutil

model_costs = {
    # Google Gemini (official ai.google.dev/pricing)
    "gemini-3.8-flash-high(high)": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.8-flash-high(medium)": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.8-flash-high(low)": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.8-flash-high": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.8-flash": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.7-flash-high(high)": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.7-flash": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.6-flash-high(high)": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.6-flash": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-2.5-flash": {"inputTokens": 0.30, "outputTokens": 2.50, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.03, "webSearchRequests": 0.01},
    "gemini-3.1-pro-low(high)": {"inputTokens": 2.00, "outputTokens": 12.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.20, "webSearchRequests": 0.01},
    "gemini-3.1-pro-low(low)": {"inputTokens": 2.00, "outputTokens": 12.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.20, "webSearchRequests": 0.01},
    "gemini-3.1-pro": {"inputTokens": 2.00, "outputTokens": 12.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.20, "webSearchRequests": 0.01},
    "gemini-2.5-pro": {"inputTokens": 1.25, "outputTokens": 10.00, "promptCacheWriteTokens": 1.25, "promptCacheReadTokens": 0.125, "webSearchRequests": 0.01},
    "agy-gemini-3-8-flash": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},

    # xAI Grok (official docs.x.ai/developers/pricing)
    "grok-4.6(xhigh)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},
    "grok-4.6(high)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},
    "grok-4.6(medium)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},
    "grok-4.6(low)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},
    "grok-4.6": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},
    "grok-4.5(high)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.30, "webSearchRequests": 0.01},
    "grok-4.5(low)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.30, "webSearchRequests": 0.01},
    "grok-4.5": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.30, "webSearchRequests": 0.01},
    "grok": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},

    # DeepSeek (official api-docs.deepseek.com/quick_start/pricing)
    "deepseek-flash[1m]": {"inputTokens": 0.30, "outputTokens": 1.20, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.006, "webSearchRequests": 0.01},
    "deepseek-flash": {"inputTokens": 0.30, "outputTokens": 1.20, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.006, "webSearchRequests": 0.01},
    "deepseek-v4.1-flash": {"inputTokens": 0.30, "outputTokens": 1.20, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.006, "webSearchRequests": 0.01},
    "deepseek-v4-pro[1m]": {"inputTokens": 1.32, "outputTokens": 3.96, "promptCacheWriteTokens": 1.32, "promptCacheReadTokens": 0.044, "webSearchRequests": 0.01},
    "deepseek-v4-pro": {"inputTokens": 1.32, "outputTokens": 3.96, "promptCacheWriteTokens": 1.32, "promptCacheReadTokens": 0.044, "webSearchRequests": 0.01},
    "deepseek-chat": {"inputTokens": 0.30, "outputTokens": 1.20, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.006, "webSearchRequests": 0.01},
    "deepseek-reasoner": {"inputTokens": 1.32, "outputTokens": 3.96, "promptCacheWriteTokens": 1.32, "promptCacheReadTokens": 0.044, "webSearchRequests": 0.01},
    "deepseek": {"inputTokens": 0.30, "outputTokens": 1.20, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.006, "webSearchRequests": 0.01}
}

paths = [
    os.path.expanduser(r"~\.claude-clg\.claude.json"),
    os.path.expanduser(r"~\.claude-clx\.claude.json"),
    os.path.expanduser(r"~\.claude-cld\.claude.json"),
    os.path.expanduser(r"~\.claude-clc\.claude.json"),
    os.path.expanduser(r"~\.claude.json")
]

for p in paths:
    d = None
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception as exc:
            print(f"WARNING: Could not parse {p} as valid JSON ({exc}). Skipping to protect file from data loss.")
            continue
        try:
            shutil.copy2(p, p + ".bak")
        except Exception:
            pass
    else:
        d = {
            "hasCompletedOnboarding": True,
            "bypassPermissionsModeAccepted": True
        }

    if not isinstance(d, dict):
        print(f"WARNING: {p} root is not a JSON object. Skipping to protect file.")
        continue

    d["hasCompletedOnboarding"] = True
    d["bypassPermissionsModeAccepted"] = True
    cache = d.setdefault("additionalModelCostsCache", {})
    if isinstance(cache, dict):
        cache.update(model_costs)
    else:
        d["additionalModelCostsCache"] = model_costs

    tmp = f"{p}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, p)
    except Exception as exc:
        print(f"ERROR: Failed to write {p}: {exc}")
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except Exception: pass
'@

$prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'SilentlyContinue'
$PricingPyScript | & $Py -
$ErrorActionPreference = $prevEAP
Write-Host "Injected real API pricing into .claude.json config caches safely via Python."

$ClcPricing = Join-Path $Here "gateway\inject_clc_pricing.py"
if (Test-Path $ClcPricing) {
    Push-Location (Join-Path $Here "gateway")
    & $Py $ClcPricing
    Pop-Location
    Write-Host "Injected clc Cursor catalog /cost rates."
}

Write-Host "`n============================================================"
Write-Host "Installation Completed Successfully!"
Write-Host "============================================================"
Write-Host "Part 1 (Worker Bridge): MCP server 'agent-visibility' registered."
Write-Host "Part 2 (Custom Launchers): clx (Grok), clg (Gemini), cld (DeepSeek), clc (Cursor) ready."
Write-Host "`nTo start a custom session:"
Write-Host "  clx   -> Grok 4.6 (500k context, Claude Code TUI)"
Write-Host "  clg   -> Gemini 3.8 Flash / 3.1 Pro (1M context, Claude Code TUI)"
Write-Host "  cld   -> DeepSeek V4.1 Flash / V4 Pro (1M context, Claude Code TUI)"
Write-Host "  clc   -> Cursor catalog in Claude Code TUI (1M, translator on 127.0.0.1:8318)"
Write-Host "         Save crsr_ key to ~/.cc-bridge/secrets/cursor-api.key"
Write-Host "         If clc still clears a file: Remove-Item Alias:clc -Force; . `$PROFILE"
