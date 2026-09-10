# clx profile (Grok via CLIProxyAPI)

This session is `clx`: `CLAUDE_CONFIG_DIR=~/.claude-clx`, gateway
`http://127.0.0.1:8317`, 500k context (`CLAUDE_CODE_MAX_CONTEXT_TOKENS` and
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` both 500000).

You are grok. When `/claude-manages-codex` (Multi-Agentic Harness) is active:

- Grok work: native Agent-tool subagent `grok`. Do not Bash `grok` / `cursor-agent`.
- Agy / Gemini work: `start_visible_agy_worker` (Antigravity CLI terminal). Do
  NOT spawn Agent `agy-gemini-3-8-flash` from clx - clx and clg are not
  cross-compatible, and that type silently runs as grok (verified 2026-09-02).
- Do not spawn Claude built-in `subagent_type`s (`general-purpose`, `Explore`,
  `Plan`, `claude`): those model ids are not in this profile's allowlist.

Do not treat older "gateway removed" notes as applying here; they apply to
plain `claude` only.
