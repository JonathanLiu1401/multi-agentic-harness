# Launchers

This directory contains launchers for running alternate provider models in the
Claude Code TUI. `clx` and `clg` talk to the local CLIProxyAPI gateway on
`http://127.0.0.1:8317`. `cld` talks to DeepSeek's Anthropic endpoint.
`clc` talks to the Cursor Anthropic translator on `http://127.0.0.1:8318`.

Your normal `claude` command and `~/.claude` profile are completely untouched
and talk directly to `api.anthropic.com`.

## Available Launchers

| Command | Provider | Primary Models | Context Window | Config Directory |
| --- | --- | --- | --- | --- |
| `clx` | xAI Grok | Grok 4.6 (xhigh/high/medium/low), 4.5 | 500k tokens | `~/.claude-clx` |
| `clg` | Antigravity (Gemini) | Gemini 3.8 Flash high, 3.1 Pro, 3.7/3.6 Flash | 1M tokens | `~/.claude-clg` |
| `cld` | DeepSeek | DeepSeek V4.1 Flash, DeepSeek V4 Pro | 1M tokens | `~/.claude-cld` |
| `clc` | Cursor | Live Cursor catalog (Grok 4.6 Fast default) | 1M (process-wide) | `~/.claude-clc` |

## Files in this Directory

- `clx` / `clg` / `cld` / `clc`: POSIX sh wrapper scripts for Git Bash (deployed to `~/bin/`).
- `clx.ps1` / `clg.ps1` / `cld.ps1` / `clc.ps1`: PowerShell wrapper scripts (deployed to `~/bin/`).
- `clx.cmd` / `clg.cmd` / `cld.cmd` / `clc.cmd`: Windows CMD shims on PATH (deployed to `~/.local/bin/`).

`clc` **is** a Claude Code profile. Cursor has no public `/v1/messages`, so
`clc` points `ANTHROPIC_BASE_URL` at `gateway/cursor_anthropic_gateway.py`
(`CLCCursorGateway` on `:8318`). PowerShell's built-in `clc` alias
(Clear-Content) is removed by the installer. Operator notes:
[`docs/setup/clc-cursor-gateway.md`](../docs/setup/clc-cursor-gateway.md).

Visible `cursor-agent` windows and Cloud Agents stay on the Part 1 MCP tools
(`start_visible_cursor_worker`, `start_cursor_cloud_agent`). Do not exec
`cursor-agent` from this launcher.

## Why Separate Launchers?

Context window sizing in Claude Code is process-wide:
- Grok's real context window is 500k tokens.
- Gemini's context window is 1M tokens.
- DeepSeek's context window is 1M tokens.
- Cursor-hosted models mostly advertise 1M; Grok 4.6 on Cursor is 500k
  natively, but `clc` still pins 1M so Opus/Sol in the same TUI are not clipped.
- `modelSettings` in `settings.json` accepts only `effortLevel` - there is no
  per-model context window key.
- `CLAUDE_CODE_AUTO_COMPACT_WINDOW` overrides any model suffix such as `[1m]`.
Therefore, each provider family runs under its own isolated profile
(`~/.claude-clx`, `~/.claude-clg`, `~/.claude-cld`, `~/.claude-clc`) to ensure
correct auto-compaction and token tracking.

## Dual-Shell Architecture on Windows

On Windows, both shells can invoke `clx`, `clg`, `cld`, or `clc` directly:
- **Git Bash** resolves `~/bin/clx` etc. (`~/bin` is in Git Bash PATH).
- **PowerShell / CMD** resolve `~/.local/bin/clx.cmd` etc.
  (`~/.local/bin` is in Windows system/user PATH). The `.cmd` shim executes
  the corresponding `.ps1` script via `powershell.exe -NoProfile -ExecutionPolicy Bypass`.
- For `clc`, also run `Remove-Item Alias:clc -Force` (or reload `$PROFILE`)
  so PowerShell does not treat `clc` as `Clear-Content`.

## Permission Posture and Speed

By default, `clx`, `clg`, `cld`, and `clc` run with `--dangerously-skip-permissions`.
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
4. **Reasoning effort**:
   - `clx` / `clg`: CLIProxyAPI `(level)` suffix on the model id.
   - `cld`: DeepSeek honors `output_config.effort` natively.
   - `clc`: translator maps `/effort` onto Cursor catalog params. Do **not**
     export `CLAUDE_CODE_EFFORT_LEVEL` (it pins the TUI and overrides saved
     `modelSettings.<id>.effortLevel`).
