# clx / clg / cld / clc: provider models in the Claude Code TUI

Set up 2026-09-02, extended 2026-09-09, Cursor dialect `clc` added 2026-09-12.
Runs Grok, Google Antigravity (Gemini), DeepSeek, and Cursor-hosted models
inside the Claude Code TUI with fully isolated config. The plain `claude`
entry point and `~/.claude` are untouched.

Owner brief: "I think claude code is the best agent harness for long horizon
reasoning tasks... this should not impact my current claude code configs."
Follow-up: "let's just stick to the default setup that the developers intended"
after judging the 2026-08 attempt as "trying to do too much".

## What runs

| Command | Provider | Primary Models | Config dir | Context | Autostart task |
| --- | --- | --- | --- | --- | --- |
| `clx` | Grok | Grok 4.5 / 4.6 | `~/.claude-clx` | 500k | `CLIProxyAPI` |
| `clg` | Gemini | Gemini 3.6/3.7/3.8 Flash, 3.1 Pro | `~/.claude-clg` | 1M | `CLIProxyAPI` |
| `cld` | DeepSeek | DeepSeek V4.1 Flash, DeepSeek V4 Pro | `~/.claude-cld` | 1M | `CLIProxyAPI` |
| `clc` | Cursor | Live Cursor catalog (Grok 4.6 Fast default, plus Fast rows) | `~/.claude-clc` | 1M (process-wide) | `CLCCursorGateway` |

One gateway serves clx/clg: CLIProxyAPI v7.2.147 at `~/cliproxyapi/`, bound to
`127.0.0.1:8317`, started at logon by `CLIProxyAPI`. `cld` talks to DeepSeek
directly. `clc` talks to a separate translator on `127.0.0.1:8318` (scheduled
task `CLCCursorGateway`). Operator detail: [`clc-cursor-gateway.md`](clc-cursor-gateway.md).

Shipped components in this repository:
- **Launchers**: `launchers/` (`clx`, `clg`, `cld`, `clc` in Bash, PS1, and CMD)
- **Gateway management**: `gateway/` (`start-gateway.ps1`, `stop-gateway.ps1`, `install-autostart.ps1`, `start-clc-gateway.ps1`, `install-clc-autostart.ps1`, `cursor_anthropic_gateway.py`)
- **Profile templates**: `templates/` (`templates/claude-clx/`, `templates/claude-clg/`, `templates/claude-cld/`, `templates/claude-clc/`)
- **Performance benchmarks & analysis**: [`docs/setup/clx-clg-perf.md`](clx-clg-perf.md)
- **Interactive TUI test suite**: `tests/tui_test.py`

Launchers live in `~/bin/{clx,clg,cld,clc}` (Git Bash) and `~/bin/{clx,clg,cld,clc}.ps1`, with
`~/.local/bin/{clx,clg,cld,clc}.cmd` shims for PowerShell/cmd. Full operator detail is in
`gateway/README.md` and `launchers/README.md`; this file documents the harness-relevant parts.

## Native subagents (the harness change)

`plugin/agents/grok.md`, `plugin/agents/agy-gemini-3-8-flash.md`, and `plugin/agents/deepseek.md` are available.
They were deleted in `2df4291` when the gateway was decommissioned; the gateway
is back, so they work again.

**Routing is profile-dependent, and clx/clg are NOT cross-compatible.**

| Captain | Same-family workers | Other-family workers |
| --- | --- | --- |
| Plain Claude (`~/.claude`) | Agent built-in `subagent_type` | grok: `start_visible_grok_worker` (Grok Build CLI). agy: `start_visible_agy_worker` (Antigravity CLI). Never native `grok` / `agy-gemini-*`. |
| clx (grok 500k) | Agent `grok` | agy: `start_visible_agy_worker`. Never Agent `agy-gemini-*`. |
| clg (Gemini 1M) | Agent `agy-gemini-3-8-flash` | grok: `start_visible_grok_worker`. Never Agent `grok`. |
| clc (Cursor 1M) | no native Agent type | Cursor: `start_visible_cursor_worker`. Cloud: `start_cursor_cloud_agent`. Never Agent `grok` / `agy-gemini-*`. |

Native Agent types run inside Claude Code's own runtime (tools, permissions,
diffs, steering, no detached console). They are same-family only. Verified
2026-09-02 from a clx session: native `grok` returned `E2E_NATIVE_GROK=OK` /
`grok-4.6(high)`; native `agy-gemini-3-8-flash` returned
`E2E_NATIVE_AGY=WRONG_MODEL` and ran as grok; visible agy CLI returned
`E2E_VISIBLE_AGY=OK` / `Gemini 3.7 Flash (High)`.

This satisfies Subagent Locality: a clx/clg session **is** Claude Code, so an
`Agent`-tool spawn of *that profile's* type is same-harness delegation. The
forbidden things are Bashing another CLI, and borrowing the other profile's
Agent type.

## Non-obvious facts, all measured

Every item here cost real debugging time. Re-verify after a Claude Code bump.

### Model picker

- **`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY` does nothing.** The binary
  guards the fetch and filters ids to `/^(claude|anthropic)/i`, so it only fills
  the picker with Claude aliases that 400 against this gateway. The launchers
  unset it.
- **Tier slots cannot be remapped.** `ANTHROPIC_DEFAULT_OPUS_MODEL` and friends
  accept only ids Claude Code already knows; pointing one at a gateway-served
  Claude id is ignored and `--model opus` still resolves to `claude-opus-5` and
  400s. Build the picker from `availableModels` + `enforceAvailableModels` +
  `modelPicker` in the profile's `settings.json` instead.
- **`modelPicker` must be an OBJECT**, not an array:
  `{"replaceBuiltInOptions": true, "options": [{"model", "label", "description"}]}`.
  A bare array is silently discarded with a settings warning, leaving only the
  single `ANTHROPIC_CUSTOM_MODEL_OPTION` row.
- **The "Default (recommended)" row cannot be removed** and always renders its id
  with a bogus `claude-` prefix. It resolves from `availableModels[0]` - not from
  `modelPicker` order and not from `ANTHROPIC_DEFAULT_MODEL` - so keep the
  intended default first in that array. Cosmetic; the labelled rows work.
- **Keep `ANTHROPIC_MODEL` set.** It overrides the `model` key from any settings
  file. Sessions often run with cwd = the home directory, which makes the main
  `~/.claude/settings.json` load as PROJECT settings, and its `"model": "opus"`
  would otherwise win on restart.

### Effort and context window

- **Reasoning effort is a CLIProxyAPI `(level)` suffix on the model id for clx/clg** -
  `grok-4.6(xhigh)`, `gemini-3.8-flash-high(medium)` - handled by the gateway.
  For DeepSeek (`cld`), the native Anthropic compatibility endpoint accepts
  Claude Code's `/effort` command directly via `output_config.effort`, so `CLAUDE_CODE_EFFORT_LEVEL`
  is omitted in `cld` to permit runtime adjustment.
- **Set `CLAUDE_CODE_EFFORT_LEVEL` in clx and clg.** The settings.json `effortLevel` key
  does not apply to non-Claude ids without native Anthropic support; without the env var
  the banner read "Grok 4.6 high with **low** effort".
- **`(level)` and `[1m]` cannot be combined** on CLIProxyAPI (the gateway 400s), and `[1m]` is
  moot anyway: `CLAUDE_CODE_AUTO_COMPACT_WINDOW` is a hard pin
  ("tokens (from settings)") and overrides the suffix.
- **Profiles isolate context windows.** Both window vars are process-wide and
  `modelSettings` accepts ONLY `effortLevel` - there is no per-model window key -
  so grok (500k), gemini (1M), and deepseek (1M) run in separate profiles.
  Verified in the TUI: clx `Auto-compact window: 500k tokens`, clg `1m tokens`, cld `1m tokens`.

### Real API cost tracking via `modelPricing`

By default, Claude Code has no built-in list prices for third-party models
(`gemini-*`, `grok-*`, `deepseek-*`). When an unrecognized model is used, Claude
Code defaults to its standard Opus 5 rate ($15/MTok input, $75/MTok output, $1.50/MTok cache read).
This artificially inflates reported spend in `/cost` and `/usage` by 20x to 150x,
and causes large prompt-cache sessions (e.g. 10M+ tokens on Gemini Flash or DeepSeek)
to show exorbitant costs.

To fix this, each profile's `settings.json` specifies `modelPricing.overrides` with official published provider rates (September 2026):
```json
"modelPricing": {
  "overrides": {
    "gemini-3.8-flash-high(high)": {
      "input": 0.75,
      "output": 3.75,
      "cacheRead": 0.075,
      "cacheWrite": 0.75
    },
    "deepseek-flash[1m]": {
      "input": 0.30,
      "output": 1.20,
      "cacheRead": 0.006,
      "cacheWrite": 0.30
    },
    "grok-4.6(high)": {
      "input": 2.00,
      "output": 6.00,
      "cacheRead": 0.50,
      "cacheWrite": 2.00
    }
  }
}
```
All four fields (`input`, `output`, `cacheRead`, `cacheWrite`) are denominated in
USD per million tokens:
- **Google Gemini** (ai.google.dev/pricing): Flash models at $0.75 in / $3.75 out / $0.075 cache read; Pro models at $2.00 in / $12.00 out / $0.20 cache read.
- **DeepSeek** (api-docs.deepseek.com/quick_start/pricing): Flash at $0.30 in ($0.15 off-peak) / $1.20 out ($0.60 off-peak) / $0.006 cache read ($0.003 off-peak); V4 Pro at $1.32 in / $3.96 out / $0.044 cache read.
- **xAI Grok** (docs.x.ai/developers/pricing): Grok 4.6 at $2.00 in / $6.00 out / $0.50 cache read (<200k tokens).
With these overrides in place, `/cost` and the status line accurately report actual API spending at configured provider rates.

### Antigravity

- **A `429 RESOURCE_EXHAUSTED` under `claude -p` is NOT quota exhaustion.** It is
  an upstream fingerprint filter on `cc_entrypoint=sdk-cli` (CLIProxyAPI issue
  #5037): print mode 429s while interactive sessions and a raw
  `POST /v1/messages` succeed on the same account and model. Observed with 96%
  weekly quota remaining, and the native `agy` CLI running the same model fine.
  Verify with a direct POST before telling the owner they are out of credits.
- `gemini-3.8-flash-medium` / `-low` are not registered upstream yet (issue
  #5423, open); only the `-high` route exists. Vary reasoning with the `(level)`
  suffix instead.

### Testing

**`claude -p` is not sufficient verification.** It never exercises the TUI, the
`/model` picker, the status line, or the settings-warning path, and every real
bug in this setup was invisible to it. It is also the one mode Antigravity
rejects, so it actively misreports which Gemini models work.

Use the interactive harness at `tests/tui_test.py` (pywinpty + pyte drive
a real PTY and render the screen):

    python tests/tui_test.py screen      # banner + settings warnings
    python tests/tui_test.py picker      # dump the /model picker
    python tests/tui_test.py ctx         # read the real context window
    python tests/tui_test.py ask "..."   # ask interactively
    CLX_CMD=clg python tests/tui_test.py screen   # target clg

Known harness gap: it cannot reliably get a prompt past the composer's
manual-mode queueing, so drive subagent checks by hand.

### Speed and Permissions Posture

A common initial impression was that clx/clg felt slow compared to native CLIs.
Rigorous instrumentation and A/B benchmarking on 2026-09-02 proved:
- **API inference is fast**: Median API call latency was 8.2s for clx and 4.7s for clg.
- **The actual bottleneck was permission prompting**: An identical 35-tool-call task took
  **10m59s** while prompting for permissions, but only **1m54s** with permissions
  bypassed (faster than Grok Build CLI at 2m34s). Nearly 9 minutes was the tool queue
  blocked waiting for user approval clicks.
- **Default posture**: The launchers now invoke Claude Code with
  `--dangerously-skip-permissions` by default, matching Grok Build CLI's `always-approve`
  behavior. `settings.json` also sets `"skipDangerousModePermissionPrompt": true`.
  Passing explicit permission flags on the command line (e.g. `clx --permission-mode plan`)
  still overrides this default.
- Full benchmarks, calls-per-turn analysis, caching, and cooldown measurements are
  detailed in [`docs/setup/clx-clg-perf.md`](clx-clg-perf.md).

### Gateway operations

Two traps, both fixed in `gateway/start-gateway.ps1`:

- **Start it detached.** A foreground child shares a console with the task's
  PowerShell wrapper, so any Ctrl+C or console close kills the gateway - seen as
  scheduled-task `lastResult=0xC000013A` (`STATUS_CONTROL_C_EXIT`) with a clean,
  error-free log tail. `Start-Process -PassThru` parents it outside any console.
- **`Stop-ScheduledTask` orphans the process**, which keeps port 8317 and makes
  the next start die on `bind: Only one usage of each socket address`. Use
  `gateway/stop-gateway.ps1`; the start script also clears survivors.

PowerShell 5.1 `*>>` redirection writes UTF-16LE, which turns a log into a binary
blob that `grep`/`tail` cannot read. Use `Add-Content -Encoding utf8`.

## Cursor: `clc` is a Claude Code dialect via a local translator

Cursor still has no public `/v1/messages` (404). CLIProxyAPI still has no
Cursor provider. The working path is **not** wrapping `cursor-agent`'s TUI
and **not** stuffing CLI bracket ids into the model field.

`clc` launches Claude Code with `CLAUDE_CONFIG_DIR=~/.claude-clc` and
`ANTHROPIC_BASE_URL=http://127.0.0.1:8318`. `gateway/cursor_anthropic_gateway.py`
implements Anthropic messages, maps Claude Code tools to Cursor SDK
`custom_tools`, and maps `/effort` plus `-fast` onto each model's catalog
params. Full operator notes: [`clc-cursor-gateway.md`](clc-cursor-gateway.md).

Verified 2026-09-12:

- Gemini 3.8 Flash + high -> dashboard `gemini-3.8-flash-high` (that model has
  no Fast param).
- Pinning `CLAUDE_CODE_EFFORT_LEVEL=high` blocks `/effort` and overrode a
  saved **low**. The launcher must not set that env var.
- Bracket model ids (`gemini-3.8-flash[reasoning_effort=high]`) 500
  `invalid_argument`. Use `ModelSelection` id + params.

Cloud Agents and visible `cursor-agent` workers stay on the Part 1 MCP tools.

## Relationship to the 2026-08-15 decommission

This knowingly reverses part of that teardown, on owner instruction. The global
CLAUDE.md line "never point `ANTHROPIC_BASE_URL` or `ANTHROPIC_AUTH_TOKEN` at a
local gateway" predates this and applies to **plain `claude`**, not to `clx` /
`clg`. What is deliberately NOT rebuilt: the `clx`/`cld`/`clg`/`clo` wrapper
sprawl of that era, the `.claude-clx`/`.claude-direct`/`.claude-ollama` triple,
the model-catalog sync scripts, and the SessionStart hooks that ran them. This
setup is stock upstream plus launchers.
