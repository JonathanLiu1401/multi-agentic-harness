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
| Default model | `~anthropic/claude-sonnet-latest[1m]` |
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
| `CLAUDE_CODE_EFFORT_LEVEL` | unset | So `/effort` maps. |
| `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY` | unset | Binary filters ids to `/^(claude\|anthropic)/i`; the picker is `settings.json`. |
| `ENABLE_TOOL_SEARCH` | `false` | Deferred custom tools 400 on non-Anthropic OpenRouter slugs. |

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

## Model picker

`templates/claude-clo/settings.json` ships a curated OpenRouter catalog
(GPT 5.6 Sol/Terra/Luna, GPT 5.5/5.4/5.3-Codex, Anthropic latest aliases,
Grok 4.6, Gemini 3.8 Flash, Kimi K3 / K2.7 Code, GLM 5.3, Qwen3.8 Max).
`modelPricing.overrides` uses live OpenRouter rates (USD per million tokens)
so `/cost` does not fall back to Opus list prices.

OpenRouter's docs say the Anthropic skin is only guaranteed with Anthropic
first-party. Direct `POST /api/v1/messages` works for GPT-5.6 Sol, but
Claude Code 2.1.273 deferred custom tools 400 on non-Anthropic slugs
(`Received openai/gpt-5.6-sol-20260709`). Default is therefore
`~anthropic/claude-sonnet-latest[1m]`. GPT/Grok/Gemini/Kimi/GLM/Qwen stay
in the picker; they will 400 until deferred tools can be turned off.

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
