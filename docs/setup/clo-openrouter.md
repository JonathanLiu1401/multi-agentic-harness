# clo: OpenRouter models in the Claude Code TUI

Added 2026-09-16. Isolated Claude Code dialect, same shape as `cld`.

`clo` talks **directly** to OpenRouter's Anthropic skin. It does not use
CLIProxyAPI on `:8317` and it does not use the Cursor translator on `:8318`.
Plain `claude` (`~/.claude`, api.anthropic.com) is untouched.

Official integration: [OpenRouter Claude Code docs](https://openrouter.ai/docs/guides/coding-agents/claude-code-integration).

## What runs

| Item | Value |
| --- | --- |
| Command | `clo` |
| Provider | OpenRouter |
| Default model | `stealth/union-alpha[1m]` |
| Config dir | `~/.claude-clo` |
| Context | 1M process-wide |
| Base URL | `https://openrouter.ai/api` (no `/v1`) |
| Auth | `ANTHROPIC_AUTH_TOKEN` from `~/.cc-bridge/secrets/openrouter-api.key` |
| Native subagent | Agent `openrouter` |

`[1m]` is a Claude Code context-window hint. OpenRouter strips it before routing.

## Required env (set by the launcher)

| Var | Value | Why |
| --- | --- | --- |
| `ANTHROPIC_BASE_URL` | `https://openrouter.ai/api` | Anthropic skin. `/v1` is the OpenAI skin and 404s `/v1/messages`. |
| `ANTHROPIC_AUTH_TOKEN` | OpenRouter `sk-or-...` key | Sent as `Authorization: Bearer`. |
| `ANTHROPIC_API_KEY` | empty string | Sent as `x-api-key`. A leftover Anthropic key bypasses OpenRouter. |
| `CLAUDE_CONFIG_DIR` | `~/.claude-clo` | Isolated profile. |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS` / `AUTO_COMPACT_WINDOW` | `1000000` | Process-wide 1M. |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | `8192` | Caps requested output tokens to 8k instead of 64k default. Leaves context headroom for sub-1M models (e.g. Union Alpha 262k). |
| `CLAUDE_CODE_EFFORT_LEVEL` | unset | So `/effort` maps. |
| `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY` | unset | Binary filters ids to `/^(claude\|anthropic)/i`; the picker is `settings.json`. |
| `ENABLE_TOOL_SEARCH` | **unset** | A custom `ANTHROPIC_BASE_URL` already disables optimistic tool-search (`not a first-party Anthropic host`). Setting `true` / `auto` / `auto:N` turns deferral back on and 400s Union Alpha / GPT. |

## Key file

Save the OpenRouter key (starts with `sk-or-`) to:

```text
~/.cc-bridge/secrets/openrouter-api.key
```

Do not put it in `cliproxyapi/config.yaml` or in git. The launcher also
accepts `OPENROUTER_API_KEY` if the file is missing.

Verified 2026-09-16: `POST https://openrouter.ai/api/v1/messages` with this
key returned `CLO_OK` for both `openai/gpt-5.6-sol` and
`~anthropic/claude-sonnet-latest`.

## Model picker (live catalog)

Every `clo` launch runs `gateway/refresh_clo_models.py`, which GETs
[`/api/v1/models?output_modalities=all&sort=most-popular`](https://openrouter.ai/docs/guides/overview/models)
and rewrites `~/.claude-clo/settings.json` `availableModels`, `modelPicker`,
and `modelPricing`. `sort=most-popular` is the same ranking as
[openrouter.ai/models](https://openrouter.ai/models) popularity (GPT-5.6 Luna,
Hy4, GLM 5.3 Flash, ...). The default `/api/v1/models` list is text-only,
capped at 500, and newest-first; this fetch is the full catalog in
popularity order (599 on 2026-09-16).

Set `CLO_SKIP_MODEL_REFRESH=1` to reuse the last picker. A failed fetch
keeps the previous settings so `clo` still starts.

Every picker id gets `[1m]` so Claude Code uses a 1M TUI window (it
assumes 200k otherwise). The row description shows OpenRouter's real
native context (`1M native`, `262k native`, ...).

The picker is A-Z by company (the `nvidia/` / `openai/` prefix), then
name. Search:

- In `/model`, press `/` to type-filter.
- `/or nemotron` is a UserPromptSubmit hook (no LLM call, so it still
  works when the key is out of inference credits).

Do not start plain `claude` and expect OpenRouter. The command is `clo`.

Starting from `$HOME` used to load `~/.claude/settings.json` as **project**
settings and pin Opus 5. The `clo` launcher now (1) sets
`ANTHROPIC_MODEL=stealth/union-alpha[1m]` and (2) if cwd is `$HOME`, cds into
`~/.claude-clo/workspace` so that leak cannot happen. You can still start
`clo` from a real project directory.

`behavesAs` maps Opus/Sonnet/Haiku/Fable families; everything else uses
`claude-sonnet-5` client handling.

OpenRouter's docs say the Anthropic skin is only guaranteed with Anthropic
first-party. Direct `POST /api/v1/messages` works for GPT-5.6 Sol, but
Do not set `ENABLE_TOOL_SEARCH`. The custom base URL already disables
optimistic tool-search. Verified 2026-09-16 in the real TUI: `clo --model
stealth/union-alpha` answered `UNION_ALPHA_OK` in 11s with no 400. Default
is `stealth/union-alpha[1m]`; `/model` can pick any other catalog slug.

## Subagent locality

| Work | From a `clo` session |
| --- | --- |
| Same-family | Agent `openrouter` |
| Grok | `start_visible_grok_worker` |
| Agy / Gemini | `start_visible_agy_worker` |
| `/claude-manages-codex` | Grok workers, never native Claude Agent types |

Do not spawn Agent `grok` / `agy-gemini-*` / `deepseek` from clo. Those
types inherit this profile's model.

## Dual-shell launchers

- Git Bash: `~/bin/clo`
- PowerShell / CMD: `~/bin/clo.ps1` via `~/.local/bin/clo.cmd`
- Default flag: `--dangerously-skip-permissions` (override with
  `--permission-mode ...`)

## Sub-1M models (e.g. Union Alpha 262k) and context headroom

OpenRouter checks `Prompt Tokens + Output Reservation <= Model Context Length`.
With Sonnet 5 client handling, Claude Code requests up to 64,000 output tokens
by default. When using a model with 262k context (like `stealth/union-alpha`),
accumulating ~200k tokens of conversation and tool schemas plus 64k output
reservation exceeds 262,144 tokens and returns HTTP 400.

`clo` sets `CLAUDE_CODE_MAX_OUTPUT_TOKENS=8192` in the launcher and settings,
leaving up to 254k tokens of input headroom for 262k models.

If a sub-1M session ever fills up and `/compact` cannot run on that model:
1. Switch to a true 1M model via `/model` (e.g. `google/gemini-3.8-flash[1m]`).
2. Run `/compact` to shrink the history down to ~5k tokens.
3. Switch back to your desired model.

## Web search (free DuckDuckGo MCP tool)

Built-in OpenRouter `WebSearch` is disabled in `disabledBuiltinTools` to avoid
OpenRouter server-side plugin fees (Exa / search billing). Web searches use
the local DuckDuckGo MCP tool (`mcp__duckduckgo__duckduckgo_search` or
`mcp__duckduckgo__web_search`), backed by `~/.cc-bridge/ddg_search_server.py`.
It is completely free, fast, and consumes zero OpenRouter credits.
