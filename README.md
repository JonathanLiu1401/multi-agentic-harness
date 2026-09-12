# Multi-Agentic Harness

A unified agentic ecosystem that combines multi-agent orchestration with multi-provider Claude Code environments.

The repository is structured into two distinct, complementary parts:
- **Part 1: The Multi-Agent Worker Bridge (`claude-manages-xxx`)**: Orchestration engine where Claude (or your manager model) serves as executive captain, architect, and reviewer while delegating implementation to visible terminal-window or headless workers across Cursor Agent, Grok Build CLI, Google Antigravity, or Claude Code runners.
- **Part 2: Provider Profiles & Gateway Launchers (`clx`, `clg`, `cld`, `clc`)**: Run alternate frontier models (xAI Grok, Google Gemini / Antigravity, DeepSeek V4.1 Flash / V4 Pro, Cursor-hosted catalog) directly inside the real Claude Code TUI with isolated profiles, dedicated context windows (500k to 1M), custom model selectors, dynamic reasoning effort, and real API cost tracking. `clc` is the Cursor dialect: Claude Code TUI on `~/.claude-clc` talking to a local Anthropic translator on `127.0.0.1:8318`. Cursor still has no public `/v1/messages`; the translator drives `cursor-sdk` so Claude Code owns tools and Cursor owns inference. Cloud Agents and visible `cursor-agent` windows remain Part 1 MCP tools. Operator notes: [`docs/setup/clc-cursor-gateway.md`](docs/setup/clc-cursor-gateway.md).

---

## One-Command Quick Install

### Windows (PowerShell)
Run from the repository root:
```powershell
powershell -ExecutionPolicy Bypass -File install-windows.ps1
```

### macOS / Linux (Bash)
Run from the repository root:
```bash
./install-macos.sh
```

### What the Installer Configures Automatically
1. **Part 1 (Worker Bridge)**:
   - Deploys `visible_agent_bridge.py`, `claude_worker_runner.py`, `cursor_worker_runner.py`, and `captain_checkup.py` to `~/.agent-bridge/`.
   - Registers the `agent-visibility` MCP server with Claude Code (`user` scope).
   - Installs the captain doctrine skill (`claude-manages-codex`) to `~/.claude/skills/`.
   - Deploys the Git Bash `cursor-agent` shim to `~/.local/bin/cursor-agent`.
2. **Part 2 (Launchers & Profiles)**:
   - Installs dual-shell launchers (`clx`, `clg`, `cld`, `clc`) to `~/bin/` (Git Bash) and `~/.local/bin/` (Windows system PATH).
   - Automatically ensures `~/.local/bin` is added to your Windows user `PATH`.
   - Creates isolated profile directories (`~/.claude-clx`, `~/.claude-clg`, `~/.claude-cld`, `~/.claude-clc`) and establishes directory junctions to share agents and skills.
   - Installs native subagent definitions (`grok.md`, `agy-gemini-3-8-flash.md`, `deepseek.md`) into `~/.claude/agents/`.
   - Deploys gateway management scripts to `~/cliproxyapi/` and initializes local security keys in `~/.cc-bridge/secrets/`.
   - Injects penny-accurate API pricing into `.claude.json` caches to eliminate Opus fallback cost inflation.

---

## Subagent Locality & Invocations

**MANDATORY RULE FOR `/claude-manages-codex` (owner directive 2026-09-11):**
When the user invokes `/claude-manages-codex`, mentions `claude-manages-codex`, or asks to use the multi-agentic harness (such as running parallel `/work-checker`, schematic review, code review, or implementation), **YOU MUST ALWAYS FAN OUT TO GROK WORKERS (`start_visible_first_mate_grok_pool` or `start_visible_grok_worker`). NEVER spawn native Claude `Agent` subagents when `/claude-manages-codex` is invoked!** Spawning native Claude subagents exhausts Anthropic session limits and burns token quotas, directly violating the purpose of invoking the harness.

When the user has NOT invoked `/claude-manages-codex` or requested the harness, routine internal delegation follows **Subagent Locality (owner rule 2026-08-15)**:

| Current Session | Default Same-Family Workers | Cross-Family / Harness Worker Routing |
| --- | --- | --- |
| **Plain Claude** (`~/.claude`, api.anthropic.com) | Routine unprompted tasks: `Agent` tool with built-in `subagent_type` (`general-purpose`, `Explore`, `Plan`, `claude`) | On `/claude-manages-codex`: ALWAYS `start_visible_first_mate_grok_pool` or `start_visible_grok_worker`<br>Grok CLI: `start_visible_grok_worker`<br>Agy: `start_visible_agy_worker`<br>Never use native `clx`/`clg`/`cld` types. |
| **clx** (`~/.claude-clx`, Grok 500k) | `Agent` tool with `subagent_type: "grok"` | Agy: `start_visible_agy_worker`<br>Grok CLI extras: `start_visible_grok_worker`<br>Never switch to clg or cld. |
| **clg** (`~/.claude-clg`, Gemini 1M) | `Agent` tool with `subagent_type: "agy-gemini-3-8-flash"` | Grok: `start_visible_grok_worker`<br>Agy CLI: `start_visible_agy_worker`<br>Never switch to clx or cld. |
| **cld** (`~/.claude-cld`, DeepSeek 1M) | `Agent` tool with `subagent_type: "deepseek"` | Grok: `start_visible_grok_worker`<br>Agy: `start_visible_agy_worker`<br>Never switch to clx or clg. |
| **clc** (`~/.claude-clc`, Cursor 1M via `127.0.0.1:8318`) | No native Agent types on this profile | Cursor workers: `start_visible_cursor_worker`. Cloud: `start_cursor_cloud_agent`. Never Agent `grok` / `agy-gemini-*` / `deepseek`. |
| **Cursor TUI** (`cursor-agent` without clc) | Native cursor-agent subagents (`cursor-grok-4.6-xhigh-fast`) | Never shell out to Claude or Grok from Cursor. |
| **Grok Build CLI** (`grok`) | Native Grok subagents | Never shell out to Claude or Cursor. |

---

# Part 1: The Multi-Agent Worker Bridge (`claude-manages-xxx`)

The Worker Bridge enables a division of labor: the manager model acts as executive architect, task decomposer, permission gatekeeper, and antagonistic reviewer, while worker backends execute implementation, codebase reconnaissance, test execution, and refactoring in visible console windows or headless runners.

### Core Capabilities
- **Visible Windows**: Runs workers in separate visible PowerShell windows so you can inspect progress, terminal outputs, and tool activity live without cluttering the manager console.
- **Run Directory Protocol**: Every run persists structured logs, events, diffs, and artifacts under `.claude-codex/runs/<run-id>/`.
- **Live Steering & Interruption**: The manager can pause, steer, or redirect an active worker using `steer_visible_*` tools without losing thread context.
- **Worker Help Mailbox**: Stuck workers can send structured requests to the captain via `request_captain_help`, allowing the captain to unblock them or prompt the user.
- **Mandatory 10-Minute Supervision**: Includes `captain_checkup.py` and `supervise_command` timers ensuring long-running workers are audited for progress rather than simple process liveness.

### Supported Worker Backends
1. **Cursor Agent (`cursor-agent`)**:
   - Preferred visible worker when the harness is explicitly requested.
   - Default model: `cursor-grok-4.6-xhigh-fast` with Cursor Max Mode enabled (1M context unlock).
   - Driven by `cursor_worker_runner.py` with tools `start_visible_cursor_worker`, `start_visible_haiku_composed_cursor_worker`, `start_visible_first_mate_cursor_pool`, `steer_visible_cursor_run`.
2. **Grok Build CLI (`grok`)**:
   - Used for Grok-specific workflows, Parallel Competition Mode, and the Mandatory Parallel Work-Checker gate.
   - Tools: `start_visible_grok_worker`, `start_visible_first_mate_grok_pool`, `steer_visible_grok_run`.
   - Supports `best_of_n` (parallel multi-candidate sampling) and `self_check`.
3. **Google Antigravity (`agy`)**:
   - Drives the standalone `agy` CLI in a visible window using your Antigravity Google credentials and separate quota.
   - Tools: `start_visible_agy_worker`, `start_visible_haiku_composed_agy_worker`, `steer_visible_agy_run`.
4. **Headless Claude Worker (`claude_worker`)**:
   - Detached headless `claude -p` worker directly against `api.anthropic.com` for long-running run-dir tasks without a GUI window.
   - Tools: `start_claude_worker`, `steer_claude_run`.
5. **Codex (`gpt-5.6-sol`)**:
   - Disabled until further notice (ChatGPT login revoked). Tools remain intact in code for reference.

---

# Part 2: Provider Profiles & Gateway Launchers (`clx`, `clg`, `cld`, `clc`)

Part 2 allows you to run third-party frontier models inside the official Claude Code CLI interface, completely preserving Claude Code's agentic loop, interactive diffs, tool calling, and slash commands while keeping configurations strictly isolated.

### Launcher Overview

| Command | Provider | Flagship Models | Context Window | Endpoint Architecture | Config Dir |
| --- | --- | --- | --- | --- | --- |
| `clx` | xAI Grok | Grok 4.6 (xhigh/high/med/low), Grok 4.5 | 500k tokens | Local CLIProxyAPI gateway (`127.0.0.1:8317`) | `~/.claude-clx` |
| `clg` | Antigravity (Gemini) | Gemini 3.8 Flash, 3.1 Pro, 3.7/3.6 Flash | 1M tokens | Local CLIProxyAPI gateway (`127.0.0.1:8317`) | `~/.claude-clg` |
| `cld` | DeepSeek | DeepSeek V4.1 Flash, DeepSeek V4 Pro | 1M tokens | Direct Anthropic API (`https://api.deepseek.com/anthropic`) | `~/.claude-cld` |
| `clc` | Cursor | Live Cursor catalog (Grok 4.6 Fast default, plus Fast rows) | 1M (process-wide) | Local Anthropic translator (`127.0.0.1:8318`) + `cursor-sdk` | `~/.claude-clc` |

### Architectural Highlights

#### 1. Why Separate Launchers?
Claude Code context windows are governed by process-wide environment variables (`CLAUDE_CODE_MAX_CONTEXT_TOKENS` and `CLAUDE_CODE_AUTO_COMPACT_WINDOW`). Furthermore, `modelSettings` in `settings.json` only accepts `effortLevel` (there is no per-model context window key). Running Grok (500k), Gemini (1M), and DeepSeek (1M) under separate profiles ensures autocompaction and context tracking are accurate for each provider.

#### 2. Dual-Shell Support on Windows
- **Git Bash**: Resolves `~/bin/clx`, `~/bin/clg`, `~/bin/cld`, and `~/bin/clc` directly from the user's `~/bin` directory.
- **PowerShell / CMD**: Resolves `~/.local/bin/clx.cmd` (and `clg`/`cld`/`clc`) from the Windows system user `PATH`. PowerShell's built-in `clc` alias is `Clear-Content`; the installer shadows it.

#### 3. Real API Cost Tracking (`modelPricing.overrides`)
When Claude Code encounters third-party model IDs, it defaults to Opus 5 list pricing ($15 input / $75 output / $1.50 cache read per MTok), creating 60x to 187x artificial cost inflation in `/cost` and `/usage`.
We resolved this by adding exact `modelPricing.overrides` and caching them in `additionalModelCostsCache` using official published rates (September 2026):
- **Google Gemini Flash (`clg`)**: $0.75 input / $3.75 output / $0.075 cache read (90% cache discount) per [Google AI pricing](https://ai.google.dev/pricing). Pro models: $2.00 input / $12.00 output / $0.20 cache read.
- **DeepSeek V4.1 Flash (`cld`)**: $0.30 input ($0.15 off-peak) / $1.20 output ($0.60 off-peak) / $0.006 cache read ($0.003 off-peak, 98% cache discount) per [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing). V4 Pro: $1.32 input / $3.96 output / $0.044 cache read.
- **xAI Grok 4.6 (`clx`)**: $2.00 input / $6.00 output / $0.50 cache read (75% cache discount) for prompts under 200k tokens per [xAI developer pricing](https://docs.x.ai/developers/pricing).
All session spending calculations reflect accurate real-world API costs.

#### 4. Dynamic Reasoning Effort
- **DeepSeek (`cld`)**: Connects directly to DeepSeek's native Anthropic Messages API, which dynamically honors Claude Code's `/effort` command and status bar effort slider.
- **Grok & Gemini (`clx` / `clg`)**: CLIProxyAPI binds reasoning effort as a model ID suffix (e.g. `grok-4.6(high)`, `gemini-3.8-flash-high(medium)`), exposed as distinct entries in the `/model` selector.
- **Cursor (`clc`)**: `/effort` maps onto each catalog param (`reasoning` / `effort` / `reasoning_effort`) plus optional `fast`. Do **not** set `CLAUDE_CODE_EFFORT_LEVEL` in the launcher: that env pins the TUI and makes `/effort` a no-op. Do **not** send CLI bracket ids (`gemini-3.8-flash[reasoning_effort=high]`); Cursor 500s those. Details: [`docs/setup/clc-cursor-gateway.md`](docs/setup/clc-cursor-gateway.md).

#### 5. Permission Posture and Speed
On complex agentic workflows, waiting for interactive user permission approvals was measured to cause 80% to 90% of total wall-clock time. Launchers default to `--dangerously-skip-permissions` with `"skipDangerousModePermissionPrompt": true` to match native CLI speed (e.g. completing 35 tool calls in 92 seconds instead of 11 minutes), while preserving command-line permission flag overrides (such as `clx --permission-mode plan`).

---

## Repository Structure

```text
multi-agentic-harness/
├── install-windows.ps1          # Automated full installer for Windows
├── install-macos.sh             # Automated full installer for macOS/Linux
├── visible_agent_bridge.py      # Part 1: Core Python MCP server (agent-visibility)
├── claude_worker_runner.py      # Part 1: Headless Claude Code worker runner
├── cursor_worker_runner.py      # Part 1: Visible Cursor Agent worker runner
├── captain_checkup.py           # Part 1: 10-minute captain supervision script
├── launchers/                   # Part 2: Launcher scripts (Bash, PS1, CMD)
│   ├── clx, clx.ps1, clx.cmd    # Grok launchers
│   ├── clg, clg.ps1, clg.cmd    # Gemini/Antigravity launchers
│   ├── cld, cld.ps1, cld.cmd    # DeepSeek launchers
│   └── clc, clc.ps1, clc.cmd    # Cursor dialect launchers
├── gateway/                     # Part 2: CLIProxyAPI + Cursor translator
│   ├── start-gateway.ps1        # Detached gateway start with port verification
│   ├── stop-gateway.ps1         # Process and scheduled task terminator
│   ├── install-autostart.ps1    # Non-elevated logon scheduled task installer
│   ├── cursor_anthropic_gateway.py # Cursor Anthropic translator (:8318)
│   ├── start-clc-gateway.ps1    # Hidden start for CLCCursorGateway
│   ├── install-clc-autostart.ps1 # Logon task for the Cursor translator
│   └── config.example.yaml      # Loopback-only CLIProxyAPI configuration template
├── templates/                   # Part 2: Claude Code profile configurations
│   ├── claude-clx/              # Grok profile (settings.json, CLAUDE.md)
│   ├── claude-clg/              # Gemini profile (settings.json, CLAUDE.md)
│   ├── claude-cld/              # DeepSeek profile (settings.json, CLAUDE.md)
│   └── claude-clc/              # Cursor profile (settings.json, CLAUDE.md)
├── plugin/
│   ├── agents/                  # Native subagent definitions
│   │   ├── grok.md              # grok-4.6 subagent
│   │   ├── agy-gemini-3-8-flash.md # gemini-3.8-flash subagent
│   │   └── deepseek.md          # deepseek-flash[1m] subagent
│   └── skills/
│       └── claude-manages-codex # Captain doctrine and spawn policies
├── docs/setup/                  # Technical deep dives and performance benchmarks
│   ├── clx-clg-gateway.md       # Gateway architecture and model picker gotchas
│   ├── clc-cursor-gateway.md    # Cursor translator, /effort, Fast, pricing
│   ├── clx-clg-perf.md          # 11-minute stall root-cause and benchmark logs
│   └── env-vars.md              # Settings.json environment documentation
├── tests/
│   ├── tui_test.py              # PTY-driven interactive TUI verification suite
│   └── e2e_visible_bridge.py    # Bridge end-to-end test suite
└── shims/
    └── cursor-agent             # Extensionless Git Bash shim for Windows
```

---

## Verification & Testing

Verify that worker backends are ready:
1. Start a Claude Code session: `claude`
2. Run the backend check MCP tool: `check_worker_backends`
3. Launch an interactive PTY screen verification for any profile:
   ```powershell
   python tests/tui_test.py screen             # Grok (clx)
   $env:CLX_CMD="clg"; python tests/tui_test.py screen  # Gemini (clg)
   $env:CLX_CMD="cld"; python tests/tui_test.py screen  # DeepSeek (cld)
   python tests/test_clc.py                            # Cursor translator health + Cloud API
   ```
4. Verify the interactive model picker:
   ```powershell
   $env:CLX_CMD="clx"; python tests/tui_test.py picker
   ```
