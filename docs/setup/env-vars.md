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
  "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "500000"
}
```

## What each var does and why it is required

| Var | Purpose | Failure without it |
|---|---|---|
| `ANTHROPIC_BASE_URL` | Routes the session through the local CLIProxyAPI gateway in **OAuth mode** (no auth-token var — the CLI sends its rotating claude.ai OAuth bearer; the proxy must run `api-keys: []` allow-all, loopback-only). | No multi-provider models. Note: settings-env wins over process env, so a "direct" escape hatch needs its own config dir + `--settings` pin, not an env override. |
| `ENABLE_TOOL_SEARCH` | Client-side deferred tool loading: MCP tool schemas are NOT sent per request (~14 tools on the wire instead of 500+); the model loads schemas on demand via a ToolSearch tool. | grok-4.5 hard-rejects any request with >350 tool definitions (`Maximum tools limit reached`). Also saves ~200k tokens of per-session MCP context. |
| `ANTHROPIC_DEFAULT_{OPUS,SONNET,FABLE}_MODEL` | Makes TYPED aliases (`/model fable`, `--model opus`) resolve to the 1M `[1m]` variants. The interactive /model picker already picks 1M; typed aliases otherwise resolve to bare 200k variants. | Typed model switches silently land on 200k context. There is NO `ANTHROPIC_DEFAULT_GROK_MODEL` — the CLI ignores it. |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS` | Sets the client-side context window for model IDs that do NOT start with `claude-` (checked after the `[1m]`/native-1M paths). Gives grok-4.5 its real ~500k window — main model, subagents, and workflow agents alike — with percentage-based autocompaction scheduled against it. Claude models keep their own catalog windows. | Unknown model IDs are budgeted at 200k (client blocks prompts past it). **Undocumented internal of the 2.1.21x builds — re-verify after every Claude Code update** (`/context` in a grok session should show ~500k). Caveat: applies to ALL non-Claude model IDs in the process; fine when grok is the only non-Claude model in play. |

## Related, deliberately NOT set

- `ANTHROPIC_AUTH_TOKEN` in the plain world — would flip the CLI to API-key
  mode and kill Remote Control everywhere. Only `clx.cmd` sets it (isolated
  world, reads the per-machine key from `proxy-key.txt` at launch).
- `CLAUDE_CODE_AUTO_COMPACT_WINDOW` — unnecessary once the window itself is
  accurate; compaction thresholds derive from the window automatically.
- `[1m]` suffix on grok in agent frontmatter — subagent model resolution can
  strip it (anthropics/claude-code#45169), and a 1M assumption would overshoot
  grok's real ceiling with no compaction safety.

## Why no automatic alternative exists (researched + refuted 2026-07-19)

- Gateway model discovery (`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY`)
  parses only `id`/`display_name` and DISCARDS model IDs not prefixed
  `claude`/`anthropic` — it cannot carry window metadata for grok.
- `ANTHROPIC_DEFAULT_*_SUPPORTED_CAPABILITIES` /
  `ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES` know only 8
  capability strings (thinking/effort/temperature families) — nothing
  window-related — and are inert behind `ANTHROPIC_BASE_URL`.
- The Anthropic-compat `/v1/models` protocol has no context-length field.
- Ollama's `ollama launch claude` hit the same wall: it ships a hardcoded
  per-model table exported as `CLAUDE_CODE_AUTO_COMPACT_WINDOW` (threshold
  only — their unknown models still meter at 200k).

## Remote Control constraint

Since Claude Code v2.1.196, Remote Control is disabled whenever the resolved
`ANTHROPIC_BASE_URL` is not `api.anthropic.com`. RC and proxy models are
mutually exclusive per session: use `cld.cmd` (direct world) for RC sessions.
Beware the project-scope leak: with cwd under the home dir, the CLI loads
`~/.claude/settings.json` as PROJECT-scope settings even under a different
`CLAUDE_CONFIG_DIR` — `cld.cmd` defeats this with `--settings
force-direct.json` (highest precedence).
