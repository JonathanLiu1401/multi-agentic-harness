# claude-manages-codex-bridge

A small Python MCP server (`visible_agent_bridge.py`) that powers the **visible-agent harness** for the
`claude-manages-codex` workflow: Claude Code's active manager model acts as captain/executive architect/QA tech lead/reviewer while OpenAI Codex
does the implementation work. The bridge launches Codex and Claude advisor sessions in visible PowerShell
windows so you can watch prompts, streamed events, agent messages, commands, token usage, and diffs live,
while also persisting logs under `.claude-codex/runs/<run-id>/`. Claude-managed visible Codex work defaults to real Codex TUI terminals so the user can steer Codex directly; the non-interactive JSON workers remain available for automation and structured event logs.

## Tools exposed

- `start_visible_codex_worker` - launch `codex exec --json` in a visible window with saved logs for automated/non-interactive runs.
- `start_visible_haiku_composed_codex_worker` - let Claude pass a compact captain brief, have Claude Haiku expand the full Codex prompt, then launch an automated/non-interactive Codex worker.
- `start_visible_first_mate_codex_pool` - launch an automated/non-interactive Codex root coordinator that spawns/manages subagents with structured logs.
- `start_interactive_codex_tui` - launch the real interactive Codex TUI in a visible terminal so the user can steer Codex directly, while the bridge records sidecar metadata.
- `start_interactive_first_mate_codex_tui` - launch the first-mate Codex coordinator in the real Codex TUI for direct user steering plus first-mate subagent orchestration.
- `steer_visible_codex_run` - queue a captain steering note into an active visible Codex run, or launch a visible resume run on the same thread if the window already closed.
- `request_captain_help` - let a stuck visible Codex worker ask the same Claude captain for feedback through the run mailbox.
- `list_captain_help_requests` / `respond_to_captain_help_request` - let Claude inspect and answer worker help requests, or escalate to the user before steering the same run.
- `submit_captain_report` / `list_captain_reports` - let interactive TUI workers hand a final report back to Claude through a sidecar artifact instead of terminal-only text.
- `start_visible_claude_advisor` - launch a visible Claude Code advisor run.
- `get_visible_run_status` / `list_visible_runs` - read status and recent log lines from a run directory.

## Current bridge behavior

- Codex workers are forced to `gpt-5.5`, `xhigh` reasoning, and `service_tier=fast`.
- Claude advisor calls use a central model policy: `fable` / `high` through July 7, 2026, then `opus` / `high`. Override with `CLAUDE_MANAGES_CODEX_ADVISOR_MODEL`.
- The Claude manager model should not write implementation code by default; it writes architecture, constraints, acceptance criteria, steering notes, and review findings.
- Long Codex delegation prompts should be written by the Haiku prompt composer, not by the manager model.
- Claude-managed visible Codex work defaults to `start_interactive_first_mate_codex_tui` for fan-out and `start_interactive_codex_tui` for single-worker direct steering.
- Use the non-interactive `start_visible_*` JSON worker tools only when Claude needs automated queued steering, structured JSONL logs, or unattended execution.
- Visible Codex workers run with full process/tool access so Python-backed skills, `read-past-sessions`, SSH, test runners, and external CLIs work. The requested `sandbox` is treated as permission intent: `read-only` means no edits, not a crippled process sandbox.
- Codex and Claude visible runs record resumable ids (`thread_id` for Codex, `session_id` for Claude).
- Claude can steer non-interactive visible Codex runs with `steer_visible_codex_run`; active JSON-worker windows consume queued steering on the same Codex thread, then close after a short idle window if no steering arrives.
- If Claude interrupts an active JSON worker, the bridge sends Ctrl+C first and resumes the same Codex thread when its session file is readable; if Codex left an empty interrupted thread, the bridge launches a fresh follow-up with the saved run context and steering instruction.
- Stuck visible Codex workers can call back to the same Claude captain with `request_captain_help`; Claude answers with `respond_to_captain_help_request` or asks the user first when owner judgment is required.
- Visible Codex workers set `NODE_PATH` and `PLAYWRIGHT_BROWSERS_PATH` so Playwright MCP and Node-based Playwright tests can run from delegated Codex sessions.
- Interactive TUI runs use top-level `codex` rather than `codex exec --json`; they are user-steered, default to `on-request` approvals, submit final handoff through `captain_reports/final.*`, and auto-close a few seconds after the report by sending Ctrl+C to the run's console with a scoped process-tree fallback.

## Firstmate skill

This repo bundles a Codex-facing Firstmate skill at [`codex-skills/firstmate/SKILL.md`](codex-skills/firstmate/SKILL.md).
It adapts the FirstMate pattern so **Claude Code is the captain**, **Codex is the first mate**, and the first mate
coordinates an ensemble of Codex agents for scouting, implementation, verification, and review.

Install/sync it locally to:

```powershell
New-Item -ItemType Directory -Force "$HOME\.codex\skills\firstmate" | Out-Null
Copy-Item .\codex-skills\firstmate\SKILL.md "$HOME\.codex\skills\firstmate\SKILL.md" -Force
```

The visible first-mate runner also embeds the same role contract, so the hierarchy still works before Codex
refreshes its skill index.

## Codex agent profiles

Custom Codex agents live under [`codex-agents/`](codex-agents/):

- `claude-explorer` - no-edit codebase scouting with Python/tool access.
- `claude-implementer` - scoped implementation after Claude grants write permission.
- `claude-reviewer` - no-edit diff and regression review.
- `claude-debugger` - full-tool SSH, device, network, serial, and command-heavy debugging when Claude explicitly allows it.

Install/sync them locally to:

```powershell
New-Item -ItemType Directory -Force "$HOME\.codex\agents" | Out-Null
Copy-Item .\codex-agents\claude-*.toml "$HOME\.codex\agents\" -Force
```

## Bundled plugin

The Claude Code plugin that drives this bridge lives under [`plugin/`](plugin/):

- `plugin/.claude-plugin/plugin.json` - plugin manifest.
- `plugin/.mcp.json` - registers the `codex-worker` (Codex MCP) and `agent-visibility` (this script) servers.
- `plugin/skills/claude-manages-codex/SKILL.md` - the `claude-manages-codex` skill: Claude as executive captain/architect/reviewer, Codex as first mate and worker harness. Includes the routing mandate that sends parallel-agent fan-out and implementation work through Codex to preserve Claude tokens.

The Codex-side advisor plugin lives under [`codex-plugin/`](codex-plugin/):

- `codex-plugin/.codex-plugin/plugin.json` - Codex plugin manifest.
- `codex-plugin/.mcp.json` - registers the visible Claude advisor bridge for Codex.
- `codex-plugin/skills/codex-consults-claude/SKILL.md` - broader Codex-to-Claude bridge contract.
- `codex-plugin/skills/claude-advisor/SKILL.md` - lightweight advisor flow for plan checks, stuck/confused states, and review.

Install or refresh it locally through your personal Codex plugin marketplace, then start a new Codex session:

```powershell
codex plugin add codex-consults-claude@personal
```

## Official OpenAI Codex plugin companion

This bridge is designed to cooperate with OpenAI's official Claude Code plugin:
[`openai/codex-plugin-cc`](https://github.com/openai/codex-plugin-cc).

Use the official plugin for stable `/codex:*` workflows:

- `/codex:setup`
- `/codex:review`
- `/codex:adversarial-review`
- `/codex:rescue`
- `/codex:transfer`
- `/codex:status`
- `/codex:result`
- `/codex:cancel`

Install it in Claude Code with:

```bash
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

Use this bridge's `start_interactive_first_mate_codex_tui` when you want the observable and directly steerable
Claude-as-captain / Codex-as-first-mate hierarchy over multiple Codex agents. Use the official `/codex:rescue` command for single
delegated rescue tasks and `/codex:review` or `/codex:adversarial-review` for standard read-only review.

## Fixes in this snapshot

This copy includes fixes over the original bridge, found while testing against Codex CLI **v0.142.2**:

1. **Removed-flag crash.** The launcher passed `codex exec ... --ask-for-approval <policy>`, a flag that
   newer Codex CLIs no longer accept. Replaced it with the config-override form
   `-c approval_policy="<policy>"`, which is accepted and equivalent.

2. **UTF-8 BOM read crash.** PowerShell's `Set-Content -Encoding UTF8` writes `status.json` with a BOM
   in Windows PowerShell 5.1. The status readers now use `encoding="utf-8-sig"` for `status.json` and
   `metadata.json`, which tolerates a BOM or its absence.

3. **UTF-8 mojibake / UTF-16 log corruption.** The detached PowerShell inherited the system OEM code page,
   and `Tee-Object` wrote `display.log` as UTF-16LE. Both runners now force UTF-8 console encoding before
   launching the child and tee through a `Write-Raw` helper (`Add-Content -Encoding UTF8`).

4. **Leaked agent runtimes.** Codex left orphaned `codex.exe`, `node.exe`, and `codex-windows-sandbox-setup.exe`
   processes alive after each run. Each run script now reaps its own descendant process tree on completion via
   `Stop-RunDescendants`, scoped strictly to descendants of that run's own PowerShell `$PID`. The Python server
   also registers an `atexit` hook that `taskkill /T /F`s every visible-run window it launched at session end.

5. **Read-only sandbox broke Python, skills, and SSH.** Visible Codex workers now get full process/tool access
   while the prompt carries a separate permission contract. A `read-only` request becomes no-edit intent, so
   Codex can still run Python, `read-past-sessions`, SSH, and repo tooling without permission to mutate files.

6. **Expensive manager-model prompt writing.** Non-trivial Codex delegation can now go through
   `start_visible_haiku_composed_codex_worker`: Claude emits a compact captain brief, Haiku/low expands the full
   worker prompt in safe mode, and Codex executes the composed prompt.

7. **Session context and resume.** Visible workers inject a session-context bootstrap and can resume prior Codex
   threads or Claude advisor sessions by id.

8. **Claude could not steer visible Codex mid-session.** Visible Codex runs now create `steer_queue/` and
   `steer_done/` directories. Claude can call `steer_visible_codex_run` to queue captain instructions into an
   active run; the same visible window consumes them on the recorded Codex thread after the current turn. If the
   window already closed, the tool starts a visible `codex resume` run against the same `thread_id`. Steering can
    also carry an updated `sandbox` permission intent when Claude moves a run from scouting to scoped writes.

9. **Visible launcher stayed stuck at `created`.** The launcher used PowerShell `-NoExit`, which could leave a
    visible shell alive while the run directory stayed locked or never advanced cleanly from the caller's view. It
    now launches with `-NoProfile` and lets the script's own short close delay control visibility and cleanup.

10. **Stuck workers had no same-captain callback.** Visible Codex prompts now include a per-run captain-help
    mailbox. A stuck worker calls `request_captain_help` and stops; Claude polls the request, can ask the user if
    the decision requires owner judgment, then `respond_to_captain_help_request` queues steering back to the same
    run/thread for non-interactive workers. Open TUI workers need direct terminal steering or a resumed TUI session
    because queued steering cannot type into an already-open TUI.

11. **Interactive TUI reports were terminal-only.** Real Codex TUI sessions do not emit `codex exec --json`
    events or `--output-last-message`, so a final answer typed into the TUI is not a reliable captain handoff.
    Interactive prompts now require `submit_captain_report`; the bridge writes `captain_reports/final.json` and
    `final.md`, exposes them through `get_visible_run_status`, and closes the TUI after the report unless the
    worker sets `close_tui=false`.

12. **Interactive TUI windows could outlive the finished agent turn.** Closing only the launcher PowerShell
    process could leave the `cmd.exe`/Codex TUI process that owned the visible terminal window. The report
    watcher now sends Ctrl+C to the run's console, waits briefly, then falls back to `taskkill /T /F` for that
    launcher tree only.

13. **Interrupt steering could race Codex's local thread store.** A forced kill could return a thread id whose
    rollout JSONL was still empty, making `codex resume` fail. Interrupt steering now tries Ctrl+C first,
    waits for a readable thread before resuming, and falls back to a fresh context-rich follow-up when the
    interrupted thread is not recoverable.

## Interactive TUI Mode

This is the default visible spawn mode for Claude-managed Codex work.

Use `start_interactive_codex_tui` when you want to type directly into a single Codex worker instead of steering through Claude or a queued bridge message. Use `start_interactive_first_mate_codex_tui` by default when you want that same direct TUI control over the Codex first mate that can coordinate Codex subagents.

This mode opens the real Codex TUI in a visible terminal. The user can approve, reject, and steer inside that terminal. The bridge still creates `.claude-codex/runs/<run-id>/` with `prompt.md`, `session_context.md`, `metadata.json`, `status.json`, `notes.md`, and best-effort `session_id.txt`.

Interactive TUI prompts include a captain handoff contract. Codex must call `submit_captain_report` before stopping, which writes `captain_reports/final.json` and `final.md`; Claude reads those through `get_visible_run_status` or `list_captain_reports`. By default the launcher watches for that report, waits about five seconds, sends Ctrl+C to the TUI console, and uses a scoped process-tree fallback if the window does not exit. Pass `auto_close_after_report=false` or `close_tui=false` when the terminal should stay open.

This mode is intentionally lower-fidelity than `codex exec --json`: `display.log` contains launcher/status lines, not a full transcript, and queued steering is not injected into an already-open TUI. For automated worker steering, structured event logs, or unattended execution, explicitly use `start_visible_codex_worker` or `start_visible_first_mate_codex_pool`.

## E2E verification

Run the full bridge E2E from the repo root:

```powershell
python .\tests\e2e_visible_bridge.py
```

The suite launches real visible runs for queued steering, closed-run resume steering, interrupt steering,
Haiku-composed Codex, first-mate Codex, and the budget-capped Claude advisor path.

## Usage

Wire it into an MCP client, such as Claude Code, by pointing at the script:

```json
{
  "mcpServers": {
    "agent-visibility": {
      "command": "python",
      "args": ["path/to/visible_agent_bridge.py"]
    }
  }
}
```

Requires the `codex` CLI on `PATH` for Codex tools and `claude` for the advisor tool.

> Note: the MCP server loads the script at startup, so after editing it you must reload/restart the MCP
> client for changes to take effect.

If you use Claude Code's permission allowlist, include the Haiku-composed worker tool alongside the older
visible-agent tools:

```json
{
  "permissions": {
    "allow": [
      "mcp__plugin_claude-manages-codex_agent-visibility__start_visible_codex_worker",
      "mcp__plugin_claude-manages-codex_agent-visibility__start_visible_haiku_composed_codex_worker",
      "mcp__plugin_claude-manages-codex_agent-visibility__start_visible_first_mate_codex_pool",
      "mcp__plugin_claude-manages-codex_agent-visibility__start_interactive_codex_tui",
      "mcp__plugin_claude-manages-codex_agent-visibility__start_interactive_first_mate_codex_tui",
      "mcp__plugin_claude-manages-codex_agent-visibility__steer_visible_codex_run",
      "mcp__plugin_claude-manages-codex_agent-visibility__request_captain_help",
      "mcp__plugin_claude-manages-codex_agent-visibility__list_captain_help_requests",
      "mcp__plugin_claude-manages-codex_agent-visibility__respond_to_captain_help_request",
      "mcp__plugin_claude-manages-codex_agent-visibility__submit_captain_report",
      "mcp__plugin_claude-manages-codex_agent-visibility__list_captain_reports",
      "mcp__plugin_claude-manages-codex_agent-visibility__get_visible_run_status",
      "mcp__plugin_claude-manages-codex_agent-visibility__list_visible_runs"
    ]
  }
}
```
