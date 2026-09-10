# clg profile (Gemini / agy via CLIProxyAPI)

This session is `clg`: `CLAUDE_CONFIG_DIR=~/.claude-clg`, gateway
`http://127.0.0.1:8317`, 1M context (`CLAUDE_CODE_MAX_CONTEXT_TOKENS` and
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` both 1000000).

You are Gemini (Antigravity). When `/claude-manages-codex` (Multi-Agentic
Harness) is active:

- Agy / Gemini work: native Agent-tool subagent `agy-gemini-3-8-flash`.
- Grok work: `start_visible_grok_worker` (Grok Build CLI terminal). Do NOT
  spawn Agent `grok` from clg - clx and clg are not cross-compatible.
- Do not spawn Claude built-in `subagent_type`s: those model ids are not in
  this profile's allowlist. Do not Bash `agy` / `grok` / `cursor-agent`.

Do not treat older "gateway removed" notes as applying here; they apply to
plain `claude` only.

A `429 RESOURCE_EXHAUSTED` under `claude -p` is the upstream
`cc_entrypoint=sdk-cli` fingerprint filter (CLIProxyAPI #5037), not quota.
Interactive sessions and raw `POST /v1/messages` are the check.
