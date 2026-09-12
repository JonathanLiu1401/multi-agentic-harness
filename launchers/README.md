# Launchers

This directory contains launchers for running alternate provider models in the
Claude Code TUI via the local CLIProxyAPI gateway on `http://127.0.0.1:8317`.

Your normal `claude` command and `~/.claude` profile are completely untouched
and talk directly to `api.anthropic.com`.

## Available Launchers

| Command | Provider | Primary Models | Context Window | Config Directory |
| --- | --- | --- | --- | --- |
| `clx` | xAI Grok | Grok 4.6 (xhigh/high/medium/low), 4.5 | 500k tokens | `~/.claude-clx` |
| `clg` | Antigravity (Gemini) | Gemini 3.8 Flash high, 3.1 Pro, 3.7/3.6 Flash | 1M tokens | `~/.claude-clg` |
| `cld` | DeepSeek | DeepSeek V4.1 Flash, DeepSeek V4 Pro | 1M tokens | `~/.claude-cld` |
| `clc` | Cursor | Cursor Grok 4.6 xhigh fast + Cloud Agents API | 1M Max Mode | n/a (native cursor-agent, not Claude Code) |

## Files in this Directory

- `clx` / `clg` / `cld` / `clc`: POSIX sh wrapper scripts for Git Bash (deployed to `~/bin/`).
- `clx.ps1` / `clg.ps1` / `cld.ps1` / `clc.ps1`: PowerShell wrapper scripts (deployed to `~/bin/`).
- `clx.cmd` / `clg.cmd` / `cld.cmd` / `clc.cmd`: Windows CMD shims on PATH (deployed to `~/.local/bin/`).
- `clc` is **not** a Claude Code profile. Cursor has no `/v1/messages` endpoint, so `clc` execs `cursor-agent` and talks to `https://api.cursor.com` for Cloud Agents. PowerShell's built-in `clc` alias (Clear-Content) is removed by the installer.

## Why Separate Launchers?

Context window sizing in Claude Code is process-wide:
- Grok's real context window is 500k tokens.
- Gemini's context window is 1M tokens.
- DeepSeek's context window is 1M tokens.
- `modelSettings` in `settings.json` accepts only `effortLevel` - there is no
  per-model context window key.
- `CLAUDE_CODE_AUTO_COMPACT_WINDOW` overrides any model suffix such as `[1m]`.
Therefore, each provider family runs under its own isolated profile
(`~/.claude-clx`, `~/.claude-clg`, and `~/.claude-cld`) to ensure correct auto-compaction and
token tracking.

## Dual-Shell Architecture on Windows

On Windows, both shells can invoke `clx`, `clg`, or `cld` directly:
- **Git Bash** resolves `~/bin/clx`, `~/bin/clg`, and `~/bin/cld` (`~/bin` is in Git Bash PATH).
- **PowerShell / CMD** resolve `~/.local/bin/clx.cmd`, `~/.local/bin/clg.cmd`, and `~/.local/bin/cld.cmd`
  (`~/.local/bin` is in Windows system/user PATH). The `.cmd` shim executes
  the corresponding `.ps1` script via `powershell.exe -NoProfile -ExecutionPolicy Bypass`.

## Permission Posture and Speed

By default, `clx`, `clg`, and `cld` run with `--dangerously-skip-permissions`.
Measured 2026-09-02:
- On an identical multi-turn task with 35 tool calls, interactive prompting took
  **10m59s** (nearly 9 minutes stalled waiting for user approval clicks on tool calls).
- The same task with permissions bypassed completed in **1m54s** (faster than
  native Grok Build CLI at 2m34s).
- API inference time was only 59 seconds across 8 calls. The bottleneck was
  queue stalling on permission prompts.

If you want a specific permission mode, pass it explicitly on the command line
(e.g., `clx --permission-mode plan`), and the command-line flag will take precedence.

## Model Picker Mechanics

1. **`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY` is unset**:
   In Claude Code, gateway discovery filters model IDs to `/^(claude|anthropic)/i`,
   filling the picker with Claude aliases that 400 against third-party gateways.
2. **Tier slots (`ANTHROPIC_DEFAULT_*_MODEL`) are not set**:
   Claude Code only accepts known Anthropic model IDs in tier slots; pointing
   them at third-party models causes 400 errors.
3. **`modelPicker` in `settings.json` must be an object**:
   Format: `{"replaceBuiltInOptions": true, "options": [{"model", "label", "description"}]}`.
   A bare array is silently ignored.
4. **Reasoning effort is passed via `(level)` suffix**:
   Handled by CLIProxyAPI (e.g. `grok-4.6(xhigh)`, `gemini-3.8-flash-high(high)`).
   `CLAUDE_CODE_EFFORT_LEVEL` is also exported in the environment.
