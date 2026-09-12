# clc: Cursor models in the Claude Code TUI

Set up 2026-09-12. `clc` is the same shape as `clx` / `clg` / `cld`: an isolated
Claude Code profile whose `ANTHROPIC_BASE_URL` points at a local translator.
Cursor still has no public Anthropic `/v1/messages` endpoint (`POST
https://api.cursor.com/v1/messages` 404s). The translator implements that
contract and drives Cursor's Python SDK (`cursor-sdk`) so **Claude Code owns
tools** and **Cursor owns inference**.

Do not confuse this with `start_visible_cursor_worker` (a visible cursor-agent
CLI window) or the Cloud Agents API (`https://api.cursor.com/v1/agents`). Those
remain Part 1 worker backends. `clc` is Part 2: you type `clc` and get the
Claude Code TUI.

## What runs

| Piece | Where | Role |
| --- | --- | --- |
| `clc` / `clc.ps1` / `clc.cmd` | `~/bin`, `~/.local/bin` | Launches `claude --dangerously-skip-permissions` with isolated env |
| Profile | `~/.claude-clc` | `CLAUDE_CONFIG_DIR`. Junctions to shared `agents` / `skills` |
| Translator | `gateway/cursor_anthropic_gateway.py` | Anthropic `/v1/messages` on `127.0.0.1:8318` |
| Autostart | scheduled task `CLCCursorGateway` | Hidden logon start, same pattern as `CLIProxyAPI` |
| Key | `~/.cc-bridge/secrets/cursor-api.key` | `crsr_` key (or `CURSOR_API_KEY`). Never commit |

```powershell
# first time
powershell -ExecutionPolicy Bypass -File "$HOME\github-tools\multi-agentic-harness\gateway\install-clc-autostart.ps1"

# every session, in PowerShell (after removing the Clear-Content alias)
Remove-Item Alias:clc -Force -ErrorAction SilentlyContinue
clc
```

If the translator is down:

```powershell
Start-ScheduledTask -TaskName CLCCursorGateway
```

PowerShell ships a ReadOnly AllScope alias `clc` -> `Clear-Content`. The
installer defines `function global:clc` in the user profile. If `clc` still
clears a file: `Remove-Item Alias:clc -Force; . $PROFILE`. `clc.cmd` always
works.

## Architecture

```
Claude Code TUI  --ANTHROPIC_BASE_URL-->  127.0.0.1:8318 translator
                                              |
                                              |  cursor-sdk AsyncClient
                                              |  tools=["mcp"]
                                              |  custom_tools = Claude Code's tools
                                              v
                                         Cursor hosted models
```

`custom_tools.execute()` blocks until the next `/v1/messages` carries the
matching `tool_result`. That is how Claude Code's Read/Bash/Edit loop stays
in Claude Code.

Do **not** put CLI bracket syntax into the model id
(`gemini-3.8-flash[reasoning_effort=high]`). Cursor returns
`invalid_argument: Cannot use this model`. Pass catalog ids plus a
`ModelSelection.params` list (`fast`, `effort` / `reasoning` /
`reasoning_effort`, `context`).

## Models, Fast, and /effort

The picker in `templates/claude-clc/settings.json` is the live Cursor catalog
(`GET https://api.cursor.com/v1/models`): every hosted id, plus a `-fast`
suffix on models that actually have a `fast` parameter (51 rows as of
2026-09-12). Default: `grok-4.6-fast`.

Cursor billing slugs are `{id}-{level}[-fast]`, for example:

| TUI pick | Cursor dashboard (when params land) |
| --- | --- |
| Grok 4.6 Fast | `grok-4.6-xhigh-fast` (effort defaults xhigh) |
| GPT-5.6 Sol Fast + high | `gpt-5.6-sol-high-fast` |
| Gemini 3.8 Flash + low | `gemini-3.8-flash-low` |
| Gemini 3.8 Flash + high | `gemini-3.8-flash-high` |

Gemini 3.8 Flash has **no** `fast` param. Fast is not missing; it does not
exist on that model. Dashboard slug `gemini-3.8-flash-high` **is** Gemini
3.8 Flash with high effort. That is not a Fast mismatch.

### Illegal Cursor variants (fast + 1m)

Cursor's `/v1/models` lists `fast` and `context` as independent params. Some
SKUs do not allow every combination. Verified 2026-09-12 against the live
catalog:

| Model | Fast + 272k | Fast + 1m | High + 1m (no Fast) |
| --- | --- | --- | --- |
| `gpt-5.6-sol`, `claude-opus-5` | yes | yes | yes |
| `gpt-5.5`, `gpt-5.4` | yes | **no** (1m is `fast=false` only) | yes |
| `gemini-3.8-flash` | n/a (no fast) | n/a | yes (`reasoning_effort`) |

If the TUI picks GPT-5.5 Fast while the translator also pins `context=1m`,
Cursor may coerce to the default SKU (`gpt-5.5-medium`, no Fast) or 500
`Cannot use this model` once the wire form is a bracket string. Prefer Sol
or Opus when you want Fast **and** 1m.

### Wire form

Pass `ModelSelection(id=..., params=[...])`. Do **not** stringify as
`id[param=value]`. Cursor returns `500 invalid_argument: Cannot use this
model: gemini-3.8-flash[reasoning_effort=high]`.

### /effort

Do **not** set `CLAUDE_CODE_EFFORT_LEVEL` in `clc.ps1`. That env var pins the
Anthropic body to `output_config.effort=<pin>` and makes `/effort` a no-op
("CLAUDE_CODE_EFFORT_LEVEL=high overrides this session"). Verified 2026-09-12:
user saved Gemini 3.8 Flash **low**, env pin sent **high**, dashboard billed
`gemini-3.8-flash-high`.

The translator reads effort in this order:

1. Request `output_config.effort` (what `/effort` sends when the env is unset)
2. `~/.claude-clc/settings.json` `modelSettings.<model>.effortLevel`
3. `CLAUDE_CODE_EFFORT_LEVEL` only if some other process exported it

Then it maps that level onto the param the catalog actually has:

- `reasoning` (GPT, Kimi, GLM)
- `effort` (Grok, Opus, Fable, Sonnet, Gemini 3.7)
- `reasoning_effort` (Gemini 3.8 Flash: `low` / `medium` / `high`)

Grok still defaults to xhigh when nothing is set. Other models do not invent
high.

## Context window

`CLAUDE_CODE_MAX_CONTEXT_TOKENS` and `CLAUDE_CODE_AUTO_COMPACT_WINDOW` are
**process-wide**. There is no per-`/model` window. `clc` pins **1m** because
most Cursor-hosted models advertise a 1m `context` param. Grok 4.6 is 500k
natively; `/context` will still show 1m in a `clc` session. That is the same
limitation that forced `clx` (500k) and `clg` (1m) apart. Pinning 500k would
clip Opus/Sol.

The translator still sends `context=1m` (or the model's max) in
`ModelSelection.params` when the catalog lists it.

## Pricing

`templates/claude-clc/settings.json` `modelPricing.overrides` uses underlying
provider list rates (September 2026) so `/cost` is not Opus-5 default. Cursor's
own dashboard often shows **Included**. Those two views will not match dollar
for dollar.

## Logs

- Translator: `~/.cc-bridge/clc-gateway.log` (look for `model=... effort=...`
  and `echoed={...}` which is Cursor's `RunResult.model`)
- Start wrapper: `~/.cc-bridge/clc-gateway-start.log`
- Child stdout/stderr: `~/.cc-bridge/clc-gateway-current.log` /
  `clc-gateway-current.err.log`

## Related

- Visible cursor-agent workers: `start_visible_cursor_worker` (Part 1)
- Cloud Agents: MCP `start_cursor_cloud_agent` / `list_cursor_cloud_agents`
- Session history: `/read-past-sessions --source clc`
