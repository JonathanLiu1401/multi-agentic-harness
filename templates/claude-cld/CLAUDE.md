# cld profile (DeepSeek via CLIProxyAPI)

This session is `cld`: `CLAUDE_CONFIG_DIR=~/.claude-cld`, gateway
`http://127.0.0.1:8317`, 1M context (`CLAUDE_CODE_MAX_CONTEXT_TOKENS` and
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` both 1000000).

You are DeepSeek (V4.1 Flash / V4 Pro). When `/claude-manages-codex` (Multi-Agentic
Harness) is active:

- DeepSeek work: native Agent-tool subagent `deepseek`.
- Grok work: `start_visible_grok_worker` (Grok Build CLI terminal).
- Agy / Gemini work: `start_visible_agy_worker` (Antigravity CLI terminal).
- Do not spawn Claude built-in subagent types: those model IDs are not in
  this profile's allowlist. Do not Bash `agy` / `grok` / `cursor-agent`.

Subagent locality: spawn same-family workers within this session's native
Agent runtime. Cross-family work routes through visible CLI terminals.
