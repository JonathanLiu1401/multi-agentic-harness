# Required settings.json env block (proxy-backed worlds)

Verified 2026-07-19 on Claude Code 2.1.215 against CLIProxyAPI 7.2.88.
These go in the `"env"` object of `settings.json` in each **proxy-backed**
world (`~/.claude` for the merged plain world, `~/.claude-clx` for clx).
The direct world (`~/.claude-direct`) gets the same block minus the proxy
base URL — shipped as `launchers/force-direct.json`, passed via `--settings`
by `cld.cmd`.

```json
"env": {
  "ANTHROPIC_BASE_URL": "http://127.0.0.1:8317",
  "ENABLE_TOOL_SEARCH": "true",
  "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-8[1m]",
  "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-5[1m]",
  "ANTHROPIC_DEFAULT_FABLE_MODEL": "claude-fable-5[1m]",
  "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "500000",
  "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "1000000"
}
```

## What each var does and why it is required

| Var | Purpose | Failure without it |
|---|---|---|
| `ANTHROPIC_BASE_URL` | Routes the session through the local CLIProxyAPI gateway in **OAuth mode** (no auth-token var — the CLI sends its rotating claude.ai OAuth bearer; the proxy must run `api-keys: []` allow-all, loopback-only). | No multi-provider models. Note: settings-env wins over process env, so a "direct" escape hatch needs its own config dir + `--settings` pin, not an env override. |
| `ENABLE_TOOL_SEARCH` | Client-side deferred tool loading: MCP tool schemas are NOT sent per request (~14 tools on the wire instead of 500+); the model loads schemas on demand via a ToolSearch tool. | grok-4.5 hard-rejects any request with >350 tool definitions (`Maximum tools limit reached`). Also saves ~200k tokens of per-session MCP context. |
| `ANTHROPIC_DEFAULT_{OPUS,SONNET,FABLE}_MODEL` | Makes TYPED aliases (`/model fable`, `--model opus`) resolve to the 1M `[1m]` variants. The interactive /model picker already picks 1M; typed aliases otherwise resolve to bare 200k variants. | Typed model switches silently land on 200k context. There is NO `ANTHROPIC_DEFAULT_GROK_MODEL` — the CLI ignores it. |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS` | Sets the client-side context window for model IDs that do NOT start with `claude-` (checked after the `[1m]`/native-1M paths). Gives grok-4.5 its real ~500k window — main model, subagents, and workflow agents alike — with percentage-based autocompaction scheduled against it. Claude models keep their own catalog windows. | Unknown model IDs are budgeted at 200k (client blocks prompts past it). **Undocumented internal of the 2.1.21x builds — re-verify after every Claude Code update** (`/context` in a grok session should show ~500k). Caveat: applies to ALL non-Claude model IDs in the process; fine when grok is the only non-Claude model in play. |

Note: bare model aliases like `grok-4.5` without `[1m]` re-trigger the 350-tool blocker and must be avoided as the main model; canonical Claude IDs carry `[1m]`.

## Related, deliberately NOT set

- `ANTHROPIC_AUTH_TOKEN` in the plain world — would flip the CLI to API-key
  mode and kill Remote Control everywhere. Only `clx.cmd` sets it (isolated
  world, reads the per-machine key from `proxy-key.txt` at launch).
- `[1m]` suffix on grok in agent frontmatter — subagent model resolution can
  strip it (anthropics/claude-code#45169), and a 1M assumption would overshoot
  grok's real ceiling with no compaction safety.

## Why no automatic alternative exists (researched + refuted 2026-07-19)

- Gateway model discovery (`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY`) adds fetched
  models to the `/model` picker but **filters to IDs matching `/^(claude|anthropic)/i`**
  and carries NO context-length metadata (the `/v1/models` protocol has no window field).
  So it surfaces `claude-*`/`anthropic-*` gateway models only — grok and `agy-gemini-*`
  are dropped — and it cannot fix grok's window (that is `CLAUDE_CODE_MAX_CONTEXT_TOKENS`'s
  job). The filter lives in the fetch/build fn that writes the cache; the cache *reader*
  `a$r()` then maps that already-filtered set (see "Model selector / picker configuration").
- `ANTHROPIC_DEFAULT_*_SUPPORTED_CAPABILITIES` /
  `ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES` know only 8
  capability strings (thinking/effort/temperature families) — nothing
  window-related — and are inert behind `ANTHROPIC_BASE_URL`.
- The Anthropic-compat `/v1/models` protocol has no context-length field.
- Ollama's `ollama launch claude` hit the same wall: it ships a hardcoded
  per-model table exported as `CLAUDE_CODE_AUTO_COMPACT_WINDOW` (threshold
  only — their unknown models still meter at 200k).

## Server-side feature-gating fallout

Since Claude Code v2.1.196, Remote Control is disabled whenever the resolved
`ANTHROPIC_BASE_URL` is not `api.anthropic.com`. RC and proxy models are
mutually exclusive per session: use `cld.cmd` (direct world) for RC sessions.
Beware the project-scope leak: with cwd under the home dir, the CLI loads
`~/.claude/settings.json` as PROJECT-scope settings even under a different
`CLAUDE_CONFIG_DIR` — `cld.cmd` defeats this with `--settings
force-direct.json` (highest precedence).
Additionally, `/autocompact` and auto-dream (the `/memory` toggle) are also gated — these are account-level GrowthBook flags, not local bugs. Remote Control specifically requires a DIRECT `api.anthropic.com` base URL, so it is blocked in proxy-backed sessions; `cld.cmd` is the direct-Anthropic escape hatch that restores `/rc`.

## Model selector / `/model` picker configuration

Verified against the 2.1.215 `claude.exe` bundle. The interactive `/model` picker lists a
fixed set of first-party **Claude slots** (Default, Opus, Fable, Sonnet, Sonnet-1M, Haiku).
Proxy models (grok, `agy-*`) are otherwise used via typed `/model <id>`, `--model`, agent
frontmatter, or the `clg` launcher. Three levers surface them IN the picker:

1. **Remap a built-in slot** — `ANTHROPIC_DEFAULT_{OPUS,SONNET,FABLE,HAIKU}_MODEL`
   (+ optional `_NAME` / `_DESCRIPTION` / `_SUPPORTED_CAPABILITIES`) points a slot at any
   model id (this is why the Opus slot already shows `claude-opus-4-8[1m]`).
2. **Add ONE custom entry** — `ANTHROPIC_CUSTOM_MODEL_OPTION` (+ `_NAME`, `_DESCRIPTION`,
   `_SUPPORTED_CAPABILITIES`) adds exactly one extra picker row (e.g. point it at
   `grok-4.5`). Singular — there is no indexed `_2` variant.
3. **Gateway discovery (claude/anthropic-prefixed only)** — `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=true`
   (add to the env block). At bootstrap Claude Code fetches `<base>/v1/models?limit=1000`,
   validates, **filters to IDs matching `/^(claude|anthropic)/i`** (regex in the fetch/build
   fn — verified 2.1.215; a second `ile()` tier filter also applies), maps them to picker rows
   (description "From gateway"), and caches `~/.claude(-clx)/cache/gateway-models.json` (the
   reader `a$r()` re-maps that already-filtered set). Gates (`Jlc()` + bootstrap):
   flag truthy (`"true"`); `vn()==="firstParty"` (OAuth/claude.ai — NOT Bedrock/Vertex/Mantle);
   `$d()` false = `ANTHROPIC_BASE_URL` is a CUSTOM gateway (not api.anthropic.com); and NOT
   `ta()` (nonessential traffic on — i.e. `DO_NOT_TRACK`/`DISABLE_TELEMETRY`/
   `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` all unset). Read at bootstrap → needs a full
   session RESTART (`/reload-plugins` does NOT trigger it; and it's async, so a `-p` run exits
   before it caches). **Result: only real `claude-*` proxy models appear** (opus-4-6/4-7/4-8,
   sonnet-4-5/4-6/5, …); **grok-4.5 and the `agy-gemini-*` pair (non-claude prefixes) are
   filtered OUT.** (The agy-Claude aliases were removed 2026-07-19 for quota reasons, so NO agy
   model appears via discovery — the surviving agy Gemini pair is non-claude.) No window metadata.

Discovery still surfaces every `claude-*` proxy model (~15: opus-4-1/4-5/4-6/4-7/4-8,
sonnet-4/4-5/4-6/5, haiku, 3-7, …), so trim the picker with a whitelist (`settings.json`
top-level keys, not env):

- **`availableModels`** (array of model-id strings) + **`enforceAvailableModels: true`**
  restrict the picker to the listed ids (managed-settings feature; non-string entries ignored;
  if the tier default isn't listed, Default resolves to the first allowed id). It only TRIMS
  the built list — it cannot ADD grok/`agy-gemini-*` that the prefix filter already dropped.
- **`modelOverrides`** remaps an Anthropic model id (e.g. `claude-opus-4-6`) to another.

To surface grok/`agy-gemini-*` in the picker: `ANTHROPIC_CUSTOM_MODEL_OPTION` adds ONE
(e.g. grok-4.5, which keeps its 500k window since the id stays non-claude); the rest use typed
`/model <id>`. Do NOT alias grok/gemini to `claude-*` just to pass the filter — that would
force them onto the ~200k catalog window.

Example — keep grok (custom slot) + your Claude defaults (agy Gemini stays typed/subagent):
```json
"availableModels": ["grok-4.5","claude-opus-4-8","claude-sonnet-5","claude-fable-5"],
"enforceAvailableModels": true
```
