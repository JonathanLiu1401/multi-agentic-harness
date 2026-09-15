# Legacy / on-request worker backends (migrated from ~/CLAUDE.md 2026-07-19; native-first 2026-07-20)

**Default spawn path is NOT here.** See SKILL.md "Which session am I in?".
Plain Claude: built-in Agent types; grok/agy via these visible CLI terminals.
clx: native Agent `grok`; agy via `start_visible_agy_worker`.
clg: native Agent `agy-gemini-3-8-flash`; grok via `start_visible_grok_worker`.
clx and clg are not cross-compatible. This file is the per-backend mechanics
for the visible-window paths.

- **grok-4.6 xhigh via grok CLI** (harness fan-out path as of 2026-09-14):
  `grok --prompt-file ... --output-format streaming-json -m grok-4.6 --reasoning-effort xhigh`; tools
  `start_visible_grok_worker` / `start_visible_haiku_composed_grok_worker` /
  `start_visible_first_mate_grok_pool` / `steer_visible_grok_run`. This is the
  visible-window and parallel fan-out path for `/claude-manages-codex`. It is
  also the path for **Parallel Competition Mode** (`competition_agents`, default
  16 in-turn competitors) and the **Mandatory Parallel Work-Checker** gate.
  Grok 4.6 xhigh fully supersedes grok 4.5. `~/.grok/config.toml` already sets
  `default = "grok-4.6"` and `default_reasoning_effort = "xhigh"`.
- **cursor-agent CLI** (EXHAUSTED 2026-09-14 - do not fan out):
  tools `start_visible_cursor_worker` / `start_visible_haiku_composed_cursor_worker` /
  `start_visible_first_mate_cursor_pool` / `steer_visible_cursor_run` remain in
  the bridge for owner-named revival only. CLI present is not quota remaining.
  Resume is `--resume <session_id>`. Read-only maps to `--mode plan`. See
  SKILL.md Review Pass.
- **Antigravity / Gemini 3.7 Flash (High)** (on request): Google `agy` CLI,
  plain-text `agy -p "..." --model "Gemini 3.7 Flash (High)"
  --dangerously-skip-permissions`; tools `start_visible_agy_worker` etc. Strong
  at coding proficiency, front-end design, and fast multi-turn coding-agent
  tasks. Effort is encoded in the model name; output is plain text, resume/steer
  best-effort via `--continue`; its Google OAuth login can go stale and demand
  interactive re-auth.
- **Codex** - **DISABLED until further notice** (owner 2026-07-15: ChatGPT login
  revoked). Do not route to Codex. `start_visible_codex_worker` /
  `_haiku_composed_codex_worker` / `_first_mate_codex_pool` /
  `steer_visible_codex_run` (model gpt-5.6-sol) remain in the code for a
  possible future revival only.
