# clo profile (OpenRouter Anthropic skin)

This session is `clo`: `CLAUDE_CONFIG_DIR=~/.claude-clo`, base URL
`https://openrouter.ai/api` (no `/v1`), 1M context
(`CLAUDE_CODE_MAX_CONTEXT_TOKENS` and `CLAUDE_CODE_AUTO_COMPACT_WINDOW`
both 1000000).

You are an OpenRouter-hosted model (default Anthropic Sonnet latest). When
`/claude-manages-codex` (Multi-Agentic Harness) is active:

- OpenRouter work: native Agent-tool subagent `openrouter`.
- Grok work: `start_visible_grok_worker` (Grok Build CLI terminal).
- Agy / Gemini work: `start_visible_agy_worker` (Antigravity CLI terminal).
- Do not spawn Claude built-in subagent types, and do not spawn Agent
  `grok`, `agy-gemini-*`, or `deepseek`: those model IDs are not in this
  profile's allowlist. Do not Bash `agy` / `grok` / `cursor-agent`.

Subagent locality: spawn same-family workers within this session's native
Agent runtime. Cross-family work routes through visible CLI terminals.

`/claude-manages-codex` still fans out to Grok workers
(`start_visible_first_mate_grok_pool` / `start_visible_grok_worker`), never
native Claude Agent types.
