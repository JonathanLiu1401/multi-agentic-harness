# Legacy / on-request worker backends (migrated from ~/CLAUDE.md 2026-07-19)

Detail for the non-default backends. The routing summary (grok-4.5 via
`start_claude_worker` preferred, Claude Sonnet fallback, Codex disabled) lives in
~/CLAUDE.md; this file holds the per-backend mechanics that only matter when
actually spawning one of these.

- **grok-4.5 via grok CLI** (legacy path, kept for grok-CLI-only extras):
  `grok --prompt-file ... --output-format streaming-json`; tools
  `start_visible_grok_worker` / `start_visible_haiku_composed_grok_worker` /
  `start_visible_first_mate_grok_pool` / `steer_visible_grok_run`. Use when you
  want **Parallel Competition Mode** (`competition_agents`, default 16 in-turn
  competitors) and the **Mandatory Parallel Work-Checker** gate — those
  injections are grok-CLI-only. Caveat: grok-4.5's `--reasoning-effort` flag
  accepts only `high`/`medium`/`low`; `xhigh` = grok's config default reached by
  omitting the flag, so the bridge omits it by default and passes only
  low/medium/high overrides.
- **Antigravity / Gemini 3.5 Flash (High)** (on request): Google `agy` CLI,
  plain-text `agy -p "..." --model "Gemini 3.5 Flash (High)"
  --dangerously-skip-permissions`; tools `start_visible_agy_worker` etc. Strong
  at coding proficiency, front-end design, and fast multi-turn coding-agent
  tasks. Effort is encoded in the model name; output is plain text, resume/steer
  best-effort via `--continue`; its Google OAuth login can go stale and demand
  interactive re-auth.
- **Codex** — **DISABLED until further notice** (owner 2026-07-15: ChatGPT login
  revoked). Do not route to Codex. `start_visible_codex_worker` /
  `_haiku_composed_codex_worker` / `_first_mate_codex_pool` /
  `steer_visible_codex_run` (model gpt-5.6-sol) remain in the code for a
  possible future revival only.
