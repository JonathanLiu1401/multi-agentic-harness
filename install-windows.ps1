# Install the Multi-Agentic Harness on Windows.
# Usage: powershell -ExecutionPolicy Bypass -File install-windows.ps1
#
# This script installs both parts of the Multi-Agentic Harness:
#   Part 1: The Multi-Agent Worker Bridge (Claude manages Cursor, Grok, Agy, and headless workers)
#   Part 2: Provider Profiles & Launchers (clx, clg, cld for Grok, Gemini, and DeepSeek in Claude Code)
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

& $Py -c "import mcp" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing python mcp package..."
    & $Py -m pip install --user mcp
}

# ---------------------------------------------------------------------------
# PART 1: Multi-Agent Worker Bridge (claude-manages-xxx)
# ---------------------------------------------------------------------------
Write-Host "`n--- Part 1: Multi-Agent Worker Bridge ---"

# 1. Deploy bridge scripts to ~/.agent-bridge/
$BridgeDir = Join-Path $UserHome ".agent-bridge"
New-Item -ItemType Directory -Force -Path $BridgeDir | Out-Null

@('visible_agent_bridge.py', 'claude_worker_runner.py', 'cursor_worker_runner.py', 'captain_checkup.py') | ForEach-Object {
    $src = Join-Path $Here $_
    if (Test-Path $src) {
        Copy-Item $src $BridgeDir -Force
    }
}
Write-Host "Deployed bridge runners to $BridgeDir"

# Compile python files to verify syntax
& $Py -m py_compile (Join-Path $BridgeDir 'visible_agent_bridge.py') (Join-Path $BridgeDir 'claude_worker_runner.py') (Join-Path $BridgeDir 'cursor_worker_runner.py') (Join-Path $BridgeDir 'captain_checkup.py')
if ($LASTEXITCODE -eq 0) {
    Write-Host "Python bridge syntax validated successfully."
}

# 2. Deploy captain doctrine skill: claude-manages-codex
$SkillSrc = Join-Path $Here 'plugin\skills\claude-manages-codex'
if (Test-Path $SkillSrc) {
    $SkillDst = Join-Path $UserHome '.claude\skills\claude-manages-codex'
    New-Item -ItemType Directory -Force -Path $SkillDst | Out-Null
    Copy-Item (Join-Path $SkillSrc '*') $SkillDst -Recurse -Force
    Write-Host "Installed skill: claude-manages-codex"
}

# 3. Register MCP server with Claude Code (user scope; idempotent)
claude mcp remove agent-visibility -s user 2>$null | Out-Null
claude mcp add agent-visibility -s user -- $Py (Join-Path $BridgeDir 'visible_agent_bridge.py')
Write-Host "Registered MCP server 'agent-visibility' (user scope)"

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
    @('clx', 'clg', 'cld', 'clx.ps1', 'clg.ps1', 'cld.ps1') | ForEach-Object {
        $f = Join-Path $LaunchersSrc $_
        if (Test-Path $f) {
            Copy-Item $f (Join-Path $BinDst $_) -Force
        }
    }
    # Windows CMD shims to ~/.local/bin
    @('clx.cmd', 'clg.cmd', 'cld.cmd') | ForEach-Object {
        $f = Join-Path $LaunchersSrc $_
        if (Test-Path $f) {
            Copy-Item $f (Join-Path $LocalBin $_) -Force
        }
    }
    Write-Host "Installed launchers (clx, clg, cld) to $BinDst and $LocalBin"
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
    @{ Name = "claude-cld"; Provider = "DeepSeek" }
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

# 6. Inject accurate model pricing into .claude.json state caches
# Official published rates (September 2026):
#   Google Gemini (https://ai.google.dev/pricing): Flash $0.75 in / $3.75 out / $0.075 cache read; Pro $2.00 in / $12.00 out / $0.20 cache read
#   xAI Grok (https://docs.x.ai/developers/pricing): Grok 4.6 $2.00 in / $6.00 out / $0.50 cache read (<200k tokens); Grok 4.5 $2.00 in / $6.00 out / $0.30 cache read
#   DeepSeek (https://api-docs.deepseek.com/quick_start/pricing): Flash $0.30 in / $1.20 out / $0.006 cache read (peak); V4 Pro $1.32 in / $3.96 out / $0.044 cache read (peak)
$modelCosts = @{
    "gemini-3.8-flash-high(high)" = @{ inputTokens = 0.75; outputTokens = 3.75; promptCacheWriteTokens = 0.75; promptCacheReadTokens = 0.075; webSearchRequests = 0.01 }
    "gemini-3.8-flash-high(medium)" = @{ inputTokens = 0.75; outputTokens = 3.75; promptCacheWriteTokens = 0.75; promptCacheReadTokens = 0.075; webSearchRequests = 0.01 }
    "gemini-3.8-flash-high(low)" = @{ inputTokens = 0.75; outputTokens = 3.75; promptCacheWriteTokens = 0.75; promptCacheReadTokens = 0.075; webSearchRequests = 0.01 }
    "gemini-3.8-flash-high" = @{ inputTokens = 0.75; outputTokens = 3.75; promptCacheWriteTokens = 0.75; promptCacheReadTokens = 0.075; webSearchRequests = 0.01 }
    "gemini-3.8-flash" = @{ inputTokens = 0.75; outputTokens = 3.75; promptCacheWriteTokens = 0.75; promptCacheReadTokens = 0.075; webSearchRequests = 0.01 }
    "gemini-3.7-flash-high(high)" = @{ inputTokens = 0.75; outputTokens = 3.75; promptCacheWriteTokens = 0.75; promptCacheReadTokens = 0.075; webSearchRequests = 0.01 }
    "gemini-3.7-flash" = @{ inputTokens = 0.75; outputTokens = 3.75; promptCacheWriteTokens = 0.75; promptCacheReadTokens = 0.075; webSearchRequests = 0.01 }
    "gemini-3.6-flash-high(high)" = @{ inputTokens = 0.75; outputTokens = 3.75; promptCacheWriteTokens = 0.75; promptCacheReadTokens = 0.075; webSearchRequests = 0.01 }
    "gemini-3.6-flash" = @{ inputTokens = 0.75; outputTokens = 3.75; promptCacheWriteTokens = 0.75; promptCacheReadTokens = 0.075; webSearchRequests = 0.01 }
    "gemini-2.5-flash" = @{ inputTokens = 0.30; outputTokens = 2.50; promptCacheWriteTokens = 0.30; promptCacheReadTokens = 0.03; webSearchRequests = 0.01 }
    "gemini-3.1-pro-low(high)" = @{ inputTokens = 2.00; outputTokens = 12.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.20; webSearchRequests = 0.01 }
    "gemini-3.1-pro-low(low)" = @{ inputTokens = 2.00; outputTokens = 12.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.20; webSearchRequests = 0.01 }
    "gemini-3.1-pro" = @{ inputTokens = 2.00; outputTokens = 12.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.20; webSearchRequests = 0.01 }
    "gemini-2.5-pro" = @{ inputTokens = 1.25; outputTokens = 10.00; promptCacheWriteTokens = 1.25; promptCacheReadTokens = 0.125; webSearchRequests = 0.01 }
    "agy-gemini-3-8-flash" = @{ inputTokens = 0.75; outputTokens = 3.75; promptCacheWriteTokens = 0.75; promptCacheReadTokens = 0.075; webSearchRequests = 0.01 }

    "grok-4.6(xhigh)" = @{ inputTokens = 2.00; outputTokens = 6.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.50; webSearchRequests = 0.01 }
    "grok-4.6(high)" = @{ inputTokens = 2.00; outputTokens = 6.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.50; webSearchRequests = 0.01 }
    "grok-4.6(medium)" = @{ inputTokens = 2.00; outputTokens = 6.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.50; webSearchRequests = 0.01 }
    "grok-4.6(low)" = @{ inputTokens = 2.00; outputTokens = 6.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.50; webSearchRequests = 0.01 }
    "grok-4.6" = @{ inputTokens = 2.00; outputTokens = 6.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.50; webSearchRequests = 0.01 }
    "grok-4.5(high)" = @{ inputTokens = 2.00; outputTokens = 6.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.30; webSearchRequests = 0.01 }
    "grok-4.5(low)" = @{ inputTokens = 2.00; outputTokens = 6.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.30; webSearchRequests = 0.01 }
    "grok-4.5" = @{ inputTokens = 2.00; outputTokens = 6.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.30; webSearchRequests = 0.01 }
    "grok" = @{ inputTokens = 2.00; outputTokens = 6.00; promptCacheWriteTokens = 2.00; promptCacheReadTokens = 0.50; webSearchRequests = 0.01 }

    "deepseek-flash[1m]" = @{ inputTokens = 0.30; outputTokens = 1.20; promptCacheWriteTokens = 0.30; promptCacheReadTokens = 0.006; webSearchRequests = 0.01 }
    "deepseek-flash" = @{ inputTokens = 0.30; outputTokens = 1.20; promptCacheWriteTokens = 0.30; promptCacheReadTokens = 0.006; webSearchRequests = 0.01 }
    "deepseek-v4.1-flash" = @{ inputTokens = 0.30; outputTokens = 1.20; promptCacheWriteTokens = 0.30; promptCacheReadTokens = 0.006; webSearchRequests = 0.01 }
    "deepseek-v4-pro[1m]" = @{ inputTokens = 1.32; outputTokens = 3.96; promptCacheWriteTokens = 1.32; promptCacheReadTokens = 0.044; webSearchRequests = 0.01 }
    "deepseek-v4-pro" = @{ inputTokens = 1.32; outputTokens = 3.96; promptCacheWriteTokens = 1.32; promptCacheReadTokens = 0.044; webSearchRequests = 0.01 }
    "deepseek-chat" = @{ inputTokens = 0.30; outputTokens = 1.20; promptCacheWriteTokens = 0.30; promptCacheReadTokens = 0.006; webSearchRequests = 0.01 }
    "deepseek-reasoner" = @{ inputTokens = 1.32; outputTokens = 3.96; promptCacheWriteTokens = 1.32; promptCacheReadTokens = 0.044; webSearchRequests = 0.01 }
    "deepseek" = @{ inputTokens = 0.30; outputTokens = 1.20; promptCacheWriteTokens = 0.30; promptCacheReadTokens = 0.006; webSearchRequests = 0.01 }
}

$ConfigFiles = @(
    (Join-Path $UserHome ".claude-clg\.claude.json"),
    (Join-Path $UserHome ".claude-clx\.claude.json"),
    (Join-Path $UserHome ".claude-cld\.claude.json"),
    (Join-Path $UserHome ".claude.json")
)

foreach ($cf in $ConfigFiles) {
    $jsonObj = $null
    if (Test-Path $cf) {
        try {
            $jsonObj = Get-Content -Raw $cf | ConvertFrom-Json
        } catch { }
    }
    if (-not $jsonObj) {
        $jsonObj = [PSCustomObject]@{
            hasCompletedOnboarding = $true
            bypassPermissionsModeAccepted = $true
        }
    }
    if (-not $jsonObj.bypassPermissionsModeAccepted) {
        $jsonObj | Add-Member -MemberType NoteProperty -Name "bypassPermissionsModeAccepted" -Value $true -Force
    }
    if (-not $jsonObj.additionalModelCostsCache) {
        $jsonObj | Add-Member -MemberType NoteProperty -Name "additionalModelCostsCache" -Value ([PSCustomObject]@{}) -Force
    }
    foreach ($m in $modelCosts.Keys) {
        $rateObj = [PSCustomObject]$modelCosts[$m]
        $jsonObj.additionalModelCostsCache | Add-Member -MemberType NoteProperty -Name $m -Value $rateObj -Force
    }
    $jsonText = $jsonObj | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($cf, $jsonText, (New-Object System.Text.UTF8Encoding $false))
}
Write-Host "Injected real API pricing into .claude.json config caches."

Write-Host "`n============================================================"
Write-Host "Installation Completed Successfully!"
Write-Host "============================================================"
Write-Host "Part 1 (Worker Bridge): MCP server 'agent-visibility' registered."
Write-Host "Part 2 (Custom Launchers): clx (Grok), clg (Gemini), cld (DeepSeek) ready."
Write-Host "`nTo start a custom session:"
Write-Host "  clx   -> Grok 4.6 (500k context)"
Write-Host "  clg   -> Gemini 3.8 Flash / 3.1 Pro (1M context)"
Write-Host "  cld   -> DeepSeek V4.1 Flash / V4 Pro (1M context)"
