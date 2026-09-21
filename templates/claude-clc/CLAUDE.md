# clc profile (Cursor via local Anthropic translator)

This session is `clc`: `CLAUDE_CONFIG_DIR=~/.claude-clc`, translator
`http://127.0.0.1:8318`, 1M context. You are a Cursor-hosted model
(default Grok 4.7 on Cursor) running inside Claude Code.

Claude Code owns tools, skills, MCP, and permissions. Cursor owns
inference. Do not Bash `cursor-agent` to do work; use this session's
tools.

When `/claude-manages-codex` is active, fan out to Grok workers via
`start_visible_first_mate_grok_pool` or `start_visible_grok_worker`.
cursor-agent usage is exhausted (2026-09-14): do **not** spawn
`start_visible_cursor_worker` / `start_visible_first_mate_cursor_pool`.
Cloud Agents (`start_cursor_cloud_agent`) only if the owner names them.
Native `grok` / `agy-gemini-*` Agent types are not on this profile.
