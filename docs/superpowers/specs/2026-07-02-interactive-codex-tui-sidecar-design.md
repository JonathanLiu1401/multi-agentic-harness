# Interactive Codex TUI Sidecar Design

## Goal

Add a hybrid launch mode that opens the real interactive Codex TUI in a visible terminal while still recording enough sidecar state for Claude to manage the work, inspect outcomes, and resume or review later.

The current visible worker uses `codex exec --json`, which is observable but not directly interactive. The new mode should use the top-level `codex` interactive CLI so the user can steer Codex directly in the terminal.

## Non-Goals

- Do not replace the existing `codex exec --json` worker path. It remains the best option for automated steering, structured JSONL logs, and E2E assertions.
- Do not promise live injection into the interactive TUI from Claude. Direct human typing in the TUI is the primary steering path for this feature.
- Do not expose hidden model reasoning. The feature should show normal Codex TUI output, session metadata, summaries, commands, diffs, and saved artifacts.
- Do not hard-code Fable. Existing time-bound Claude advisor model policy remains separate.

## User Experience

Claude starts a new visible interactive Codex run with a compact captain brief and session context. A PowerShell window opens running the real Codex TUI. The user can type directly into Codex, approve or reject interactive prompts, and use normal Codex TUI behavior.

The bridge returns a run directory under `.claude-codex/runs/<run-id>/`. Claude records that directory in the bridge ledger and can inspect it later.

Expected tool result fields:

- `ok`
- `run_dir`
- `cwd`
- `prompt`
- `metadata`
- `session_context`
- `note`

## New MCP Tool

Add `start_interactive_codex_tui`.

Suggested arguments:

- `prompt`: compact initial instructions for the Codex TUI.
- `cwd`: workspace directory.
- `session_context`: compact current-session context.
- `sandbox`: permission intent, default `workspace-write` only when Claude is confident; otherwise `read-only`.
- `requires_tool_access`: when true, use the full-tool process posture already used by visible workers.
- `resume_session_id`: optional Codex session id to continue with `codex resume <id>`.
- `approval_policy`: optional interactive approval policy. Default `on-request` for TUI sessions so the user can approve or reject actions directly.
- `model`: accepted for API symmetry, but the tool should force `gpt-5.6-sol`.
- `reasoning_effort`: honored per run; validated against `high` / `xhigh` / `max` / `ultracode` and defaulted to `xhigh` when missing or unrecognized (Claude selects the tier by task difficulty).
- `service_tier`: accepted for API symmetry, but the tool should force `fast`.
- `no_alt_screen`: optional boolean. When true, pass `--no-alt-screen` so terminal scrollback remains easier to inspect.
- `close_on_exit`: optional boolean. Default false for interactive use, so the terminal remains visible after Codex exits.

## Launch Command

For a new session, launch top-level interactive Codex:

```powershell
codex -m gpt-5.6-sol -C <cwd> -s <effective-sandbox> -a on-request -c model_reasoning_effort="<tier>" -c service_tier="fast" <prompt>
```

For resume:

```powershell
codex resume <session-id> -m gpt-5.6-sol -C <cwd> -s <effective-sandbox> -a on-request -c model_reasoning_effort="<tier>" -c service_tier="fast" <optional-prompt>
```

Use `codex.cmd` when resolving the executable on Windows, matching the existing bridge behavior.

The effective process sandbox should keep the current bridge policy: full local tool access where needed, while the prompt carries the permission contract. If `sandbox` is `read-only`, that means no edits unless the user explicitly authorizes them inside the TUI.

## Sidecar Files

Create the same run directory structure used by visible workers, plus TUI-specific files:

- `prompt.md`: initial TUI prompt.
- `session_context.md`: compact context passed to Codex.
- `metadata.json`: launch args, cwd, permission intent, forced model settings, process id, and timestamps.
- `status.json`: `created`, `running`, `closed`, `failed`, or `unknown`.
- `session_id.txt`: best-effort discovered Codex session id.
- `notes.md`: human-readable run notes and post-run summary slot.
- `display.log`: optional launcher/status log, not a full TUI transcript.

The TUI itself may not expose structured JSON events. The sidecar must not pretend to have the same log fidelity as `codex exec --json`.

## Session ID Capture

Session id capture should be best effort:

1. Record start time and `CODEX_HOME`.
2. After launch, inspect the newest Codex session files under the local Codex session directory.
3. Match by timestamp, cwd, prompt snippet, or metadata when available.
4. Write the detected id to `session_id.txt` and `metadata.json`.
5. If no id is found, keep the run usable and report `session_id: null`.

Claude can still ask the user to paste a visible session id if Codex shows one and automatic detection fails.

## Claude Management Semantics

Claude uses this mode when the user wants to steer Codex directly. Claude remains the architect and reviewer, but direct live steering belongs to the user.

Claude should:

- provide concise architecture, scope, non-goals, and verification criteria in the launch prompt
- record the run in `.claude-codex/BRIDGE.md`
- avoid sending duplicate steering through `steer_visible_codex_run` for an interactive TUI run
- inspect the resulting session artifacts, git diff, tests, and sidecar notes before final claims
- resume the TUI session with `start_interactive_codex_tui(..., resume_session_id=...)` when continuation is needed

## Error Handling

- If `codex` is not found, return a clear error with the resolved PATH check.
- If the terminal launches but no session id can be detected, return `ok: true` with `session_id: null` and a note.
- If resume id is provided but Codex rejects it, write the failure to `display.log` and set `status.json` to `closed` or `failed`.
- If the process remains open, status should be `running` until a watcher observes exit. If no watcher is available, report `unknown` rather than false certainty.

## Tests

Unit-style tests:

- validate command construction for new TUI sessions
- validate command construction for resumed sessions
- validate metadata and sidecar file creation
- validate session-id discovery fallback when no session file is found
- validate forced model settings

Manual/E2E tests:

- launch a real Codex TUI in a visible terminal
- type a short message directly into the TUI and confirm Codex responds
- exit the TUI and confirm sidecar status updates
- resume the same session id and confirm continuity
- verify existing `codex exec --json` E2E still passes

## Rollout

1. Add the new tool without changing existing visible worker behavior.
2. Document that interactive TUI mode is user-steered and lower-fidelity than JSON exec mode.
3. Sync live bridge script and Claude skill.
4. Update README and permission allowlist examples.
5. Run existing E2E plus targeted TUI sidecar tests.
6. Commit and push after verification.
