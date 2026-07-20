---
name: claude-manages-codex
description: Multi-Agentic Harness — use when Claude Code should act as executive architect, QA tech lead, first-mate captain, and reviewer while delegating implementation, exploration, subagent orchestration, codebase reading, mechanical refactors, test repair, or cheap iteration to a worker backend through the bundled agent-visibility MCP server. The PREFERRED worker MODEL is grok-4.5, spawned windowless via a native grok subagent (Agent tool, subagent_type "grok", proxy-backed sessions) or via start_claude_worker (headless claude -p through the local CLIProxyAPI gateway, any model); Claude Sonnet subagents are the fallback; legacy visible-window backends (grok CLI, Google Antigravity / Gemini 3.5 Flash) remain for CLI-only extras or on request; Codex is disabled until further notice. Trigger for requests like "have Claude manage the worker", "delegate this to grok", "use grok/sonnet/gemini as the worker", "parallelize with subagents", "ask the worker to implement", "spawn a first-mate pool", "show or steer visible worker logs", "first mate", "multi-agent harness", or any coding task where Claude makes high-level decisions and a worker does low-level work.
---

# Multi-Agentic Harness (internal id: claude-manages-codex)

> **Rename note (2026-07-15, updated 2026-07-18):** this skill is now branded the **Multi-Agentic Harness** to reflect that it drives multiple worker backends, not just Codex. As of 2026-07-18 the harness gained two windowless spawn paths — native grok subagents in the Claude Code CLI, and headless `claude -p` workers via `start_claude_worker` through the local CLIProxyAPI gateway — which are now the preferred way to delegate; the original visible-PowerShell-window backends (grok CLI, Antigravity/agy, Codex) are legacy/on-request. See "Worker Backends & Routing" below for the current routing policy. Its internal id / MCP tool prefix / install directory remain `claude-manages-codex` for tool-name, permission-allowlist, and install compatibility — a full id-level rename is a separate breaking change. Much of the prose below still says "Codex" because Codex was the original backend; read it as "the worker backend" where the text predates the newer backends.

Use Claude's active manager model as captain, executive architect, QA tech lead, and reviewer. Delegate the low-level work to a worker backend — by default **grok-4.5**, spawned windowless via a native grok subagent or `start_claude_worker` (see "Worker Backends & Routing") — including root sessions and native subagents.

## Core Model

- Claude owns architecture, task decomposition, acceptance criteria, risk calls, worker assignment, active steering, and final review. In the first-mate flow, Claude is the captain.
- **The worker owns cheap exploration, first-pass implementation, test repair, mechanical refactors, and noisy command/log work.** The default worker is **grok-4.5**, spawned windowless via a native grok subagent (`subagent_type: "grok"`) or `start_claude_worker(model="grok-4.5")`; Claude Sonnet subagents are the fallback; the agy fleet is the next fallback ladder; **Codex is disabled** (see "Worker Backends & Routing").
- Claude may orchestrate native subagents (the `Agent` tool — including `subagent_type: "grok"` and the `agy-*` fleet) and **Workflows** directly for parallel fan-out (see the Routing Mandate), or delegate to a windowless worker backend. The legacy visible-CLI first-mate pools remain for their CLI-only extras or on request.
- Claude must review worker output and local diffs before claiming completion — antagonistically for grok (see "grok-4.5 rigor and mandatory adversarial review").
- Prefer delegating through a worker backend over doing implementation directly in the manager loop.
- The Claude manager model does not write implementation code by default. It writes plans, contracts, constraints, acceptance tests, review findings, steering notes, and the final user response. Route code edits to the worker (default grok-4.5) unless the edit is tiny, the backend is unavailable, or the user explicitly asks Claude to code directly.
- Claude sets the worker's reasoning effort per task by judged difficulty. Token savings come from routing work off the manager and matching effort to difficulty, not from weakening the worker on hard tasks. (Effort ladders differ by backend — grok's CLI caps at `low`/`medium`/`high`; `start_claude_worker` and agy accept `low`…`max`. See "Reasoning Effort Policy".)
- Every new or resumed worker run receives session context. Pass a compact `session_context`, and tell the worker to use `read-past-sessions` before acting when it needs the full transcript.
- Workers run with full process/tool access by default so Python-backed skills, `read-past-sessions`, SSH, and developer CLIs work. Use the requested `sandbox` as permission intent: `read-only` means no edits (enforced for grok/claude_worker), not a crippled process sandbox.
- SSH, serial, live-device, hardware, network, Docker, package-manager, and external-tool debugging must set `requires_tool_access: true` or `sandbox: danger-full-access`.
- Do not spend manager-model output tokens on boilerplate, long worker prompts, or raw-log analysis a worker can do. For the legacy visible-CLI backends, pass a compact captain brief to the Haiku prompt composer.
- The preferred spawn path is **windowless**: a native grok subagent (`subagent_type: "grok"`) in a proxy-backed session, or `start_claude_worker(model="grok-4.5", ...)` for any model. The legacy visible-CLI workers (`start_visible_*`) run in PowerShell windows with structured JSONL logs, direct steering, completion watchers, and captain-help mailboxes — kept for their CLI-only extras (grok Competition Mode / Work-Checker) or on request. The interactive TUI tools are deprecated. **Codex spawn tools are disabled** — do not use them.
- Hidden model reasoning is not displayable. Surface useful progress, summaries, commands, and implementation state instead.

## Worker Backends & Routing (added 2026-07-14, windowless paths added 2026-07-18)

This bridge supports these worker backends and spawn paths behind the same run-dir mechanics (run directories, `display.log`, `events.jsonl`, `status.json`, steering, captain-help, captain reports, `get_visible_run_status`, `list_visible_runs`):

- **Native grok subagent** — the headline windowless path (added 2026-07-18). `Agent` tool, `subagent_type: "grok"`, defined by `agents/grok.md`. Only in a proxy-backed session. See "Native grok subagent backend" below.
- **`start_claude_worker` (headless `claude -p`)** — the general windowless backend and the **PREFERRED default spawn path** (added 2026-07-18). Detached headless Claude Code CLI processes routed through the local CLIProxyAPI gateway; `model` honors any proxy model, not just grok. See "Headless claude_worker backend" below.
- **Grok CLI (grok-4.5, legacy visible-window)** — kept for the grok-CLI-only extras: Parallel Competition Mode and the Mandatory Parallel Work-Checker gate (see below). `start_visible_grok_worker`, `start_visible_haiku_composed_grok_worker`, `start_visible_first_mate_grok_pool`, `steer_visible_grok_run`. Full mechanics also summarized in `references/legacy-backends.md`.
- **Claude Sonnet** — an in-process Claude Agent-tool subagent. No CLI, no auth, no run-dir machinery; always available. The **fallback** worker: use when the proxy/grok is unavailable/capped, or when a task genuinely needs a Claude-only capability.
- **Antigravity / Gemini 3.5 Flash (agy, legacy visible-window)** — `start_visible_agy_worker`, `start_visible_haiku_composed_agy_worker`, `steer_visible_agy_run`. CLI present and authenticated (`agy.exe`, `~/.gemini/oauth_creds.json`), reachable through `check_worker_backends`. **On request.** Gemini 3.5 Flash is highly optimized for coding proficiency, front-end design, and complex multi-turn coding-agent tasks. See "Antigravity / Gemini (agy) Worker Backend" below and `references/legacy-backends.md`.
- **Codex (gpt-5.6-sol)** — the historically original backend, referenced throughout the older prose below. **DISABLED until further notice (owner 2026-07-15): there is no more Codex** — its ChatGPT login is revoked and it is not to be used. The tools and code are left intact so it can be revived later, but do not route to Codex; `check_worker_backends(deep=True)` will report it unavailable.

### Default routing policy (2026-07-18)

Unless the owner says otherwise:

- **Default worker MODEL = grok-4.5. Default SPAWN PATH = windowless.** In a proxy-backed `clx` session, prefer the **native grok subagent** (`subagent_type: "grok"`). Otherwise, or for any non-grok model, use `start_claude_worker(model="grok-4.5", ...)` — the tool's own default model is `claude-opus-4-8`, so pass `model="grok-4.5"` explicitly for default grok work.
- **Fall back to a Claude Sonnet subagent** (the `Agent` tool) when the proxy/grok is unavailable, capped, or the task needs a Claude-only capability.
- **Use the legacy grok-CLI visible-window path** specifically when a task needs its CLI-only extras — Parallel Competition Mode or the Mandatory Parallel Work-Checker gate (see below) — which `start_claude_worker` spawns do not carry.
- Use **Antigravity (agy)** when the owner explicitly asks or when grok-4.5 is exhausted: 2 native Gemini subagents (`agy-gemini-3-1-pro`, `agy-gemini-3-5-flash`) draw the agy account's separate quota (see "Native agy subagent backend" below). grok-4.5 still routes first (grok-4.5 > agy Gemini). The legacy visible-window agy path stays for on-request terminal runs. **Do not use Codex — it is disabled.**
- **Always call `check_worker_backends` before delegating.** Never assume a backend is usable just because its CLI exists on disk or the proxy is running. If the preferred backend is unavailable, fall back to a Claude Sonnet subagent and tell the user why.

### Native grok subagent backend (added 2026-07-18)

Spawn with the `Agent` tool, `subagent_type: "grok"`. Defined by `agents/grok.md`: frontmatter pins `model: grok-4.5` and a deliberately small toolset (Read, Write, Edit, Bash, Grep, Glob, TodoWrite, NotebookEdit, WebFetch, WebSearch) — grok-4.5 rejects any request carrying more than 350 tools, and a full plain session can expose far more than that across loaded MCP servers, so the toolset is kept narrow on purpose.

- Appears in Claude Code's own agent list; steer it natively with `SendMessage` (no external process, no window, no `steer_visible_*` tool needed).
- **Precondition:** only works in a proxy-backed session (the `clx` launcher, or a plain session merged with the proxy) whose endpoint actually serves grok. In a plain direct-Anthropic session grok is not a valid native-subagent model — use `start_claude_worker(model="grok-4.5")` there instead.
- `agents/grok.md` bakes the Worker Rigor Contract and a no-further-delegation rule directly into the agent's own system prompt (it is itself a spawned worker and must not delegate further, spawn its own subagents, or re-invoke this skill).
- **Context window (verified 2026-07-19, claude 2.1.21x):** grok subagents and workflow agents get grok-4.5's accurate **~500k window** via `CLAUDE_CODE_MAX_CONTEXT_TOKENS=500000` in the settings.json `env` block (set in the plain and clx worlds). That undocumented env var applies only to model IDs not starting with `claude-` (checked after the `[1m]`/native-1M paths), so grok resolves to 500k with default percentage-based autocompaction against it while Claude models in the same process keep their own catalog windows. Without it, Claude Code budgets unknown model IDs at 200k, and no other mechanism exists (gateway model discovery reads only `id`/`display_name` and discards non-`claude`/`anthropic` ids; capability env vars are inert behind `ANTHROPIC_BASE_URL`; `/v1/models` has no context-length field — Ollama's `ollama launch claude` hit the same wall and ships a hardcoded table exported as `CLAUDE_CODE_AUTO_COMPACT_WINDOW`). Do NOT put `grok-4.5[1m]` in agent frontmatter: subagent resolution can strip the suffix (anthropics/claude-code#45169), and a 1M assumption would overshoot the real 500k ceiling with no compaction safety. Re-verify the env var after Claude Code version bumps (undocumented internal). Main-model grok sessions: use the **`clg`** launcher (`~\.local\bin\clg.cmd`: bare `grok-4.5`, window from the same env var).

### Native agy subagent backend (added 2026-07-19)

Two Google Antigravity **Gemini** models are wired as **native Claude Code subagents** (Agent tool, `subagent_type`), served through CLIProxyAPI's **antigravity** OAuth channel — the non-terminal alternative to `start_visible_agy_worker`. Each draws the agy account's **SEPARATE** quota, never the owner's real Claude/Anthropic subscription. Defined by `~/.claude/agents/agy-*.md` (deployed from repo `plugin/agents/`, junction-shared into `~/.claude-clx`).

- Subagents (capability order): `agy-gemini-3-1-pro` > `agy-gemini-3-5-flash` (Gemini 3.1 Pro / 3.5 Flash High). The agy Claude 4.6 models (opus/sonnet) are deliberately NOT wired — their Antigravity quota bucket's limits are too low to be usable (see Quota below). Owner rule of thumb: `agy-gemini-3-5-flash` = speedy ops, `agy-gemini-3-1-pro` = harder/slower.
- **Routing:** grok-4.5 FIRST (grok-4.5 > agy Gemini); use agy on grok-exhaustion or explicit request. Like any native subagent, only in a proxy-backed session (plain merged / clx).
- **Quota:** the two wired Gemini subagents draw the {gemini flash, pro} bucket (ample — ~96%+ free in practice). The other bucket {Claude opus, sonnet, gpt-oss} has very low limits — its 5-hour window exhausts fast (observed at 0% while Gemini had ~96%) — so the Claude 4.6 models AND GPT-OSS 120B are served but deliberately UNWIRED. Gemini rides free quota.
- **Context windows:** each Gemini subagent pins `<id>[1m]` → ~1M client window (Gemini is natively ~1M). If `[1m]` is stripped in subagent resolution (anthropics/claude-code#45169) the fallback is safe (agy-*→500k global) — under-budget, never overflow.
- **Setup** (`-antigravity-login` + `oauth-model-alias.antigravity` config + the config-needs-a-proxy-RESTART caveat, since Windows fsnotify misses the atomic-save config edit): `docs/setup/agy-antigravity.md`. New agent files need `/reload-plugins` (or restart) to appear in a running interactive session; fresh `claude -p` / workers pick them up automatically. Verified e2e 2026-07-19.
- **Operational caveats:** large-context agy calls occasionally return a **malformed HTTP 200** through the proxy — treat an empty/malformed body as a retry/fallback signal, not success. (The agy Claude 4.6 models were dropped because their bucket's 5-hour limit exhausts too fast to be usable — see Quota above.)

### Headless claude_worker backend (added 2026-07-18)

`start_claude_worker` is the general windowless backend and the preferred spawn path when the native grok subagent path doesn't apply (non-grok models, non-proxy sessions needing a fallback, etc.). Implemented by `claude_worker_runner.py`, which builds a `claude -p --verbose --output-format stream-json --permission-mode <mode> --add-dir <cwd> [--model][--effort] ...` invocation, passes the prompt via STDIN, and sets `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` (from `proxy.json`) and `CLAUDE_CONFIG_DIR` in the child environment — no terminal window opens.

Full live signature: `start_claude_worker(prompt, cwd, title="Claude worker", model=CLAUDE_WORKER_DEFAULT_MODEL ("claude-opus-4-8"), sandbox="read-only", effort="", session_context="", resume_session_id="", max_budget_usd="", steer_idle_seconds=20, use_proxy=True)`.

- `model`: any model the local CLIProxyAPI gateway (`127.0.0.1:8317`, ~38 models as of 2026-07-19) serves — `grok-4.5`, `claude-opus-4-8`, `claude-sonnet-5`, `claude-fable-5`, etc. — honored exactly as passed. The tool's own default is `claude-opus-4-8`, so pass `model="grok-4.5"` explicitly for default grok work.
- `sandbox` maps to Claude Code CLI permission modes: `read-only` -> `plan` (+ `Write`/`Edit` stripped, enforced not just requested), `workspace-write` -> `acceptEdits`, `danger-full-access` -> `bypassPermissions`.
- `effort`: `low` / `medium` / `high` / `xhigh` / `max`.
- `steer_claude_run(run_dir, instruction, ..., interrupt_current_turn=False)` steers or resumes a run mid-flight. Unlike the visible steers (which interrupt the in-flight turn by DEFAULT), its `interrupt_current_turn` defaults to **False** (queue/resume-oriented) — pass `True` to interrupt. There is no `requires_tool_access` param.
- `use_proxy=False` bypasses the proxy for a direct-Anthropic spawn.
- Full run-dir protocol preserved: `events.jsonl`, `display.log`, `status.json`, `captain_reports/`, `captain_help/`, `steer_queue/` — the same backend-agnostic `get_visible_run_status` / `list_visible_runs` / `submit_captain_report` / `list_captain_reports` / `request_captain_help` / `list_captain_help_requests` / `respond_to_captain_help_request` tools every other backend uses.
- `check_worker_backends` reports a `claude_worker` entry (proxy reachable + model count) alongside `claude_sonnet` / `grok` / `codex` / `agy`.
- Every claude-worker prompt (any model, including grok-4.5 via this tool) auto-carries the Worker Rigor Contract — see "grok-4.5 rigor and mandatory adversarial review" below — but NOT the grok-CLI-only Parallel Competition Mode / Mandatory Parallel Work-Checker extras (`competition_agents`, `best_of_n`, `self_check` are grok-CLI params, not `start_claude_worker` params). Escalate a hard problem to the legacy grok-CLI backend when those extras are wanted.

### Memory (claude-mem) integration (added 2026-07-18)

Headless `claude -p` workers spawned by `start_claude_worker` run under an isolated Claude config dir (e.g. `~/.claude-clx`) with the `claude-mem` plugin enabled. Because of that, claude-mem's SessionStart/PostToolUse/Stop hooks fire for those workers automatically, and their prompts/session-init get passively captured into the shared claude-mem store (the global daemon on `127.0.0.1:37777` backing a SQLite DB + vector store) — no bridge code change needed. Keep this conservative:

- Observation *richness* depends on run length — a short worker turn may produce few or no distilled observations.
- The non-Claude CLI backends (grok CLI, agy CLI) are not Claude Code processes, so they fire no claude-mem hooks and their work is not captured.
- Native `subagent_type: "grok"` **and `agy-*`** subagents run inside the parent Claude Code session, so only that parent session's own claude-mem capture (plugin `claude-mem@thedotmack`) covers their top-level activity.

### Leveraging SuperGrok Heavy (grok "heavy mode")

There is no separate `heavy` CLI flag or model id — SuperGrok Heavy (owner is tier 5) is a subscription tier that raises grok's compute/rate limits, and grok exposes that power through its agent system, which the bridge already uses:

- **Native subagents are ENABLED by default** on every grok worker (the bridge never passes `--no-subagents`), so a single `start_visible_grok_worker` can already spawn parallel child agents ("uses agents efficiently") when the task warrants it.
- **`start_visible_first_mate_grok_pool`** is the explicit fan-out path — a grok root that coordinates native subagents, the grok analog of the first-mate pool.
- **`best_of_n` param** (wired 2026-07-15) on `start_visible_grok_worker` / `start_visible_haiku_composed_grok_worker`: pass `best_of_n=N` (capped 1–6) to run the initial task N ways in parallel and keep the best (`--best-of-n`, initial turn only). The concrete Heavy-tier quality lever — but it costs ~N× tokens, so reserve it for hard, high-value tasks.
- **`self_check` param** (wired 2026-07-15): pass `self_check=True` to append grok's own self-verification loop (`--check`) to the initial turn — a cheap quality boost on top of Claude's review.
- **`[subagents]` config** in `~/.grok/config.toml` (per-agent model pins, roles, personas) is a further lever tuned outside the bridge.

### Strict read-only enforcement (grok)

For a grok worker launched with `sandbox="read-only"`, the bridge now **enforces** no-edit by passing `--disallowed-tools Write,Edit` so Grok's file-mutation tools are removed — it truly cannot edit, not merely asked not to (borrowed from faeton/claude-grok-plugin). Bash is intentionally kept so read-only inspection (Python-backed skills, read-past-sessions, safe read commands) still works — the bridge's read-only means "no edits", not "no commands". Use `read-only` for scouting / second-opinion / review workers; use `workspace-write` or full access when the worker must edit.

*(These three — read-only enforcement, `best_of_n`, `self_check` — were adopted 2026-07-15 after surveying existing grok↔Claude Code plugins; the multimodal / xAI-API-key / older-model-tier features from those plugins were intentionally not adopted, since this harness runs the newer grok-4.5 via the SuperGrok Heavy OAuth CLI.)*

### grok-4.5 rigor and mandatory adversarial review (owner assessment 2026-07-15)

**grok-4.5 is a fast coder but a weak engineer** — roughly gpt-5.3-codex-spark class. Its observed failure modes: it fixates on a single hypothesis, does not consider multiple scenarios, skips edge cases and error paths, and declares work "done" without ever executing it end to end. Treat every grok result as **unverified and probably buggy until you prove otherwise.** Two mechanisms enforce this:

1. **Worker Rigor Contract (automatic).** Every grok worker prompt is prepended with a mandatory contract (`_grok_rigor_contract`) that forces the worker to: enumerate 2-3 hypotheses/approaches and the edge/error/boundary cases before coding; adversarially pressure-test its own change; **actually run it end to end and paste the observed output as proof** (a confident "done" without executed evidence is defined as a failure); and report what it did NOT test plus the top 2 ways it could still be wrong. You do not need to add this to your brief — it is always injected — but your `prompt_brief` should still name the concrete acceptance test and the specific scenarios/edge cases you want covered.

2. **Mandatory Opus-captain adversarial review (you).** Do NOT trust grok's "done." Review its diff and claims **antagonistically, assuming they are wrong**, and specifically:
   - Independently VERIFY end to end yourself — run the tests / CLI / endpoint / repro, read the real output. Grok's own "I tested it" is not sufficient evidence; grok's self-check (`--check`) is weak self-marking, not proof.
   - Hunt the cases grok most likely skipped: the edge/empty/null/boundary inputs, the error branch, concurrency, the opposite of the happy path, and the scenario it fixated away from.
   - Check for tunnel vision: did it fix the reported symptom while missing the root cause or breaking an adjacent case?
   - If it drifted, fixated, or reported success without executed proof, reject and re-steer with the specific missing case — or escalate: raise `reasoning_effort`, set `self_check=True`, or use `best_of_n=2-3` so grok generates and self-selects among multiple attempts on hard tasks.
   - Only report a grok result to the user as done after YOU have executed the acceptance test and seen it pass. This is not optional for grok — it is the primary defense against its weaknesses.

For non-trivial or correctness-sensitive grok work, prefer `best_of_n` (multiple scenarios) and `self_check=True` (its own verify pass) on top of your adversarial review — but they supplement, never replace, the captain's independent e2e verification.

### Parallel Competition Mode (grok-4.5, up to 16 in-turn competitors)

grok usage is abundant and resets often, so lean on parallelism to compensate for grok-4.5's weak single-shot reasoning. Every grok worker prompt carries a **Parallel Competition Mode** contract (`_grok_competition_contract`, controlled by the `competition_agents` param, default 16, cap 16): for a HARD or open-ended problem the root worker spawns up to N diverse subagents **inside its single turn** (native grok subagents — one terminal, no extra windows, so the owner is not spammed), each independently attempting the full task with a different strategy; the root then acts as judge, discards competitors that lack executed evidence, and **compiles the best result** (picks the strongest or synthesizes a superior combination), then verifies the compiled result end to end. This is the grok-4.5 analog of the grok-4.20 multi-agent harness.

- It is judgment-gated: the contract tells grok to compete only when the task is hard enough to benefit and to solve simple/mechanical tasks directly, so it does not fan out 16 agents to reply with a token.
- Set `competition_agents=1` to disable competition for a run (e.g. trivial or strictly-sequential tasks); set 2-16 to cap the competitor count.
- It composes with the rest: competitors still obey the Rigor Contract (run + prove), and the Opus captain STILL independently e2e-verifies the compiled result — a grok-run competition that picks a winner is not a substitute for the captain's own verification.
- `competition_agents` is a prompt capability, not a CLI flag; it stacks with `best_of_n` (a CLI-level N-way retry) but the two overlap, so prefer one lever at a time unless a task is genuinely huge.

### Mandatory parallel work-checker (grok, every run)

Every grok worker prompt also carries a **Mandatory Parallel Work-Checker** contract (`_grok_work_checker_contract`, always injected) that fires right before the worker may report done: it must spawn a fleet of parallel checker subagents inside the same turn (one terminal), each adversarially auditing its OWN finished work from a different lens (correctness/logic, edge cases & error paths, did-it-actually-run/re-execute the acceptance test, requirements coverage, regressions/blast-radius, and security/concurrency/perf where relevant), then consolidate the proven findings (no cry-wolf), **fix every real issue, and re-run the checkers until they come back clean.** A grok worker may not declare done until a clean parallel work-checker pass, and its report must include what the checkers found, what it fixed, and the final clean verification output. This is the automatic, worker-side counterpart to the captain's own adversarial review — it directly attacks grok-4.5's "declares done without testing" habit. (It is judgment-scaled: a purely trivial informational reply self-verifies instead of spawning a full fleet.) The captain STILL independently e2e-verifies after — the worker's self-run checker is not a substitute for the captain's verification.

### `check_worker_backends`

`check_worker_backends(cwd=None, deep=False) -> {"claude_sonnet": {...}, "claude_worker": {...}, "grok": {...}, "codex": {...}, "agy": {...}}`, one `{available, reason, detail}` record per backend.

- Default (`deep=False`) is cheap: CLI path existence, auth-file presence/parseability, and (for Codex) local JWT-expiry decoding. No network calls.
- The `claude_worker` entry checks that the local CLIProxyAPI gateway is reachable and reports the number of models it serves — call this before delegating to `start_claude_worker` or a native grok subagent, exactly like the other backends.
- `deep=True` additionally runs one short live `codex exec` round trip (roughly 5-15s, a trivial no-tool prompt) that catches server-side token revocation a locally-valid JWT hides. Grok and agy do not get a live ping in `deep` mode — their file-based expiry/refresh-token check is already reliable, and a live ping would spend a real prompt turn for no better signal.
- Observed live on this machine (2026-07-14): `claude_sonnet`, `grok`, and `agy` available; `codex` available=False under `deep=True` with reason `"codex not logged in (ChatGPT login lost / token revoked server-side)"` — the ChatGPT session was revoked while the local access-token JWT and `codex login status` both still looked fine, which is exactly the case `deep=True` exists to catch.

### Callback model (Grok and Antigravity/agy workers)

(`start_claude_worker`'s own report/callback behavior is covered by the general run-dir protocol in "Headless claude_worker backend" above — the run-dir carries `captain_reports/` for every backend. This subsection covers the two legacy visible-window backends specifically.)

Every non-Codex backend's worker gets a result back to Claude through two layers:

1. **Layer 1 — runner auto-report (robust, always on).** The Grok and agy PowerShell runners each write `captain_reports/final.json` + `final.md` themselves from the worker's own answer text after every turn, independent of whether the worker ever calls an MCP tool. `get_visible_run_status` and `list_captain_reports` read it the same way they read a Codex `submit_captain_report` call. For agy this is the ONLY callback path (see below); for Grok it is the always-on fallback under Layer 2.
2. **Layer 2 — live MCP callback.** Where wired (Grok: `~/.grok/config.toml` `[mcp_servers.agent-visibility]`, pointed at the deployed bridge), the worker prompt also instructs the model to call `submit_captain_report` / `request_captain_help` mid-run, matching the Codex `codex-consults-claude` pattern. The shared allowlist in `submit_captain_report` and `request_captain_help` was widened from `metadata.agent in (None, "codex")` to `(None, "codex", "grok", "agy")`, so a Grok (or agy, once/if wired) worker's live call is accepted and surfaces through `list_captain_reports` / `list_captain_help_requests` exactly like a Codex call. Codex behavior is unchanged; the codex-only `steer_visible_codex_run` gate stays codex-specific (Grok/agy steer through their own `steer_visible_*_run` tools). **agy has NO Layer 2 wired**: `agy --help` exposes no `mcp` subcommand, and the only MCP-shaped file found on this machine, `~/.gemini/config/mcp_config.json`, is 0 bytes with no schema documented anywhere reachable — editing it blindly to guess a schema would risk the owner's real authenticated agy config for an unverified guess, so this was deliberately left unwired (checked live 2026-07-14; revisit if `agy` ever ships an `mcp` subcommand or documents the config file). The agy worker prompt does NOT tell the model to call `submit_captain_report`/`request_captain_help` (unlike Codex/Grok prompts), since it has no way to reach them.

> ⚠️ **Reading everything below (Reasoning Effort Policy → Claude Review Standard):** these sections document worker mechanics — effort tiers, the manager loop, steering, the 10-minute supervision cadence, completion watchers, run ownership, captain-help, permission intent, delegation-pattern templates, token efficiency, the bridge ledger, and the review standard — using **Codex (`gpt-5.6-sol`) as the historical example backend**. **Codex is DISABLED** (owner 2026-07-15). These mechanics are **backend-agnostic**: apply them to the active worker (native grok subagent, `start_claude_worker`, or agy), mapping "Codex" → "the worker", `start_visible_codex_worker` / `start_visible_first_mate_codex_pool` → the backend's spawn path (`subagent_type: "grok"` / `start_claude_worker` / a Workflow), and `steer_visible_codex_run` → the backend's steer tool (`steer_claude_run`, `SendMessage` for native subagents, or `steer_visible_grok_run` / `steer_visible_agy_run`). The run-dir protocol, watchers, supervision, ownership, and review standard are identical across backends. The Routing Mandate and Worker-Exhaustion Fallback below are updated in place to be worker-first; the older tool-reference sections keep Codex naming under this mapping.

## Reasoning Effort Policy

Codex runs on `gpt-5.6-sol`. Claude — the manager — chooses the Codex reasoning effort per task by judging its difficulty. Effort is no longer pinned to `xhigh`; Claude scales it up or down along this ladder:

- `high`: routine, low-ambiguity work — mechanical refactors, formatting, narrow test repair, small well-scoped edits, cheap scouting where the answer is easy to find.
- `xhigh`: normal multi-file implementation, non-trivial exploration, moderate debugging, and reviews with some ambiguity. This is the default floor when Claude does not specify.
- `max`: hard problems — subtle concurrency/correctness bugs, cross-cutting refactors, tricky architecture-sensitive changes, or work where a wrong answer is expensive.
- `ultra`: the hardest, highest-stakes tasks — deep multi-subsystem reasoning, gnarly root-cause hunts, or large coordinated changes. `ultra` is `gpt-5.6-sol`'s top effort tier: instead of only spending more chain-of-thought in a single turn, it natively decomposes the problem into cooperative internal subagents (see below). It costs significantly more tokens per turn and is preview-gated, so reserve it for genuinely hard, parallelizable work. Ultra runs are intentionally unbudgeted — do not cap them with a token or dollar budget (owner decision 2026-07-14).

(`minimal`, `low`, and `medium` are also valid `model_reasoning_effort` values the bridge accepts, but Codex worker tasks in this bridge should stay on the `high` → `ultra` range above unless Claude has a specific reason to go lower.)

How Claude selects:

- Assess difficulty yourself before dispatching: scope (files/subsystems touched), ambiguity, blast radius of a mistake, and how much independent reasoning the worker must do. Pick the lowest tier that comfortably covers the task; escalate when the signals are high.
- Pass the chosen tier as `reasoning_effort` (or `config.model_reasoning_effort`) on the Codex/visible/TUI start tools. The bridge validates it against `gpt-5.6-sol`'s accepted values (`minimal` / `low` / `medium` / `high` / `xhigh` / `max` / `ultra`) and falls back to the `xhigh` floor if it is missing or unrecognized.
- Re-judge on steering. If a task turns out harder than expected (repeated failed attempts, confused workers, growing scope), raise the effort on the next run or resume; if it turns out trivial, drop it. Do not leave everything at one fixed tier.
- Match effort to the worker's job, not just the overall goal: a cheap `claude-explorer` scout can run at `high` while the `claude-implementer` doing the hard change on the same goal runs at `max` or `ultra`.

### Ultra effort and native subagent fan-out

At `ultra` effort, `gpt-5.6-sol` decomposes the work into its own cooperative internal subagents and reassembles the result — the model-native equivalent of the first-mate pool. Use it when Claude has judged the task hard and genuinely parallelizable (independent subsystems, a wide search, or a large coordinated change). For a Codex root/first-mate coordinator, `ultra` also backs its explicit `claude-explorer` / `claude-implementer` / `claude-reviewer` fan-out (file-disjoint for writes).

Keep it bounded and captain-governed:

- Claude authorizes `ultra` and the fan-out in the brief; a worker does not unilaterally escalate its own effort tier or spawn a deep subagent tree.
- Respect the existing fan-out cap (at most the worker count Claude requested, otherwise 6) and the no-recursive-trees rule — ultra widens a single layer, it does not nest layers.
- Prefer one `ultra` run over spraying many separate high-effort workers for genuinely parallelizable work. Do not attach a rollout token budget or any other spend cap to an `ultra` run — the owner removed the ultra budget limit (2026-07-14); the bounds on `ultra` are scope and the fan-out cap, not tokens.
- Lower tiers (`high` / `xhigh` / `max`) run as single workers unless Claude explicitly asks for a small parallel split.

## Official OpenAI Codex Plugin

This bridge is designed to work with OpenAI's official Claude Code plugin at `https://github.com/openai/codex-plugin-cc`.

Use the official `codex` plugin when it is installed and the task matches one of its standard workflows:

- `/codex:setup`: check local Codex CLI readiness and authentication; use this before first use or when Codex errors suggest missing setup.
- `/codex:review`: read-only review of current work or branch diff.
- `/codex:adversarial-review`: read-only challenge review that pressure-tests implementation direction, assumptions, tradeoffs, and risk areas.
- `/codex:rescue`: delegate a substantial investigation, bug fix, or follow-up task to Codex through the official companion runtime.
- `/codex:transfer`: transfer the current Claude Code session into a resumable Codex thread.
- `/codex:status`, `/codex:result`, `/codex:cancel`: manage official plugin background jobs.

Installation path for the official plugin:

```bash
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

Do not copy the official plugin command scripts into this plugin just to expose `/codex:*`; that namespace belongs to the official plugin. If the official plugin is not installed, use this bridge's bundled MCP tools and visible-agent harness as the fallback and tell the user the official plugin can be installed with the commands above.

Use this bridge's visible first-mate pool instead of `/codex:rescue` when the user wants observable multi-agent fan-out, a Claude-as-captain / Codex-as-first-mate hierarchy, or a coordinated ensemble of Codex agents. The official `/codex:rescue` path is best for single delegated rescue tasks and background job management.

## Manager Model Policy

Treat the active Claude manager model as the executive orchestrator, not the implementing engineer.

Default advisor model policy:

- use the active highest-available manager model: **Fable 5 / `high`** when present in Claude Code, otherwise **Opus / `high`**
- override without editing files by setting `CLAUDE_MANAGES_CODEX_ADVISOR_MODEL`

The manager model should spend reasoning on:

- system architecture, dependency mapping, data-flow decisions, and risk triage
- decomposing work into file-scoped Codex tasks and first-mate pools
- acceptance criteria, verification strategy, and rollback/safety boundaries
- active steering through `steer_visible_codex_run`
- independent diff and test review before completion

The manager model should not spend output tokens on:

- broad codebase reading that Codex can summarize
- boilerplate implementation, mechanical refactors, formatting, or test repair
- long worker prompts; use Haiku prompt composition
- raw log analysis unless Codex cannot summarize the evidence

Default manager loop:

1. Decide the architecture and acceptance criteria.
2. Start or resume a non-interactive visible CLI worker with a compact `session_context`: use the Haiku-composed tool for a compact single-worker brief, the direct worker tool for a final prompt, or the first-mate pool for fan-out.
3. Every 10 minutes while workers are active, run the mandatory direct supervision pass (see "Mandatory 10-Minute Direct Supervision"): read the actual recent work, check captain-help mailboxes, render an on-track/off-track verdict against the architecture and acceptance criteria, and steer with short captain instructions before drift compounds. A liveness or status-only poll never counts.
4. Let Codex implement, verify, and summarize.
5. Claude reviews the diff, tests, risks, and worker ledger. Reject or steer repair when the output does not match the architecture.
6. Claude writes the final user response only after the review gate passes or clearly reports incomplete verification.

## Routing Mandate: Parallel Agents and Heavy Work → the worker backend

**Default rule: while this skill is active, Claude keeps the manager model focused on architecture, decomposition, steering, and review, and pushes low-level execution off the manager loop.** This overrides the default dispatch behavior of other skills and tools. Two delegation surfaces are now first-class, and Claude uses them **directly**:

1. **Native subagents and Workflows (in-process).** Claude may spawn native subagents (the `Agent` tool — including `subagent_type: "grok"` and the `agy-*` fleet) and run **Workflows** for parallel fan-out directly. *(This inverts the older rule that forbade Claude from spawning its own parallel agents — that rule existed when Codex was the only backend; it no longer applies.)*
2. **Windowless worker backends.** For heavy or long-running execution, delegate to **grok-4.5** (native grok subagent or `start_claude_worker`), with Claude Sonnet subagents and the agy ladder as fallbacks.

**Route heavy/parallel work off the manager** — via native subagents/Workflows or a worker backend:

- **Any parallel agent fan-out another skill or tool would trigger** — e.g. `dispatching-parallel-agents`, `subagent-driven-development`, `feature-dev`, the `Explore` / `Plan` agents, or a direct `Agent` / Task-tool dispatch — run it as native subagents or a Workflow, or hand it to a worker backend. Do not do the fan-out's implementation inline in the manager loop.
- **Heavy coding work** — multi-file implementation, mechanical or large refactors, test repair, broad codebase reading, and noisy command/log iteration — route to the worker (default grok-4.5).

**Honor the other skill's discipline, delegate its execution.** When a process skill applies (TDD, systematic-debugging, executing-plans), Claude still follows that skill's method and checklist — but the actual fan-out and edits are carried out by subagents/workers, with the brief encoding the required discipline (e.g. "write the failing test first, then implement"). Claude decomposes, writes the briefs, and reviews; the workers execute.

**Claude keeps (never delegate):** architecture, task decomposition, acceptance criteria, risk and security calls, steering decisions, final review of every diff, and the user-facing response.

**Delegation is ONE level deep.** A spawned subagent/worker (grok, agy, Sonnet, claude_worker) must not delegate further, spawn its own subagents, or re-invoke this skill — only the top-level manager delegates. This is what prevents infinite agent loops.

**Do the work in the manager loop only when:**

- The edit is tiny (single file, a few lines) where delegation overhead exceeds the token savings and the user has not asked for strict delegation.
- The work needs tools or context only Claude can reach (MCP servers the worker lacks, this session's live state).
- Every worker backend is unavailable/capped — fall back to doing it directly and tell the user.
- The user explicitly asks Claude to do the work directly.

When delegating to a windowless backend, prefer the **native grok subagent** (`subagent_type: "grok"`, steered with `SendMessage`) or **`start_claude_worker`** (any proxy model; steered with `steer_claude_run`; arm its returned `watch_command`). The legacy visible-CLI pools (`start_visible_*`) remain for their CLI-only extras or an explicit request to watch a terminal.

## Parallel Fan-Out Contract

The bridge runs workers concurrently: start tools return within about a second and simultaneous workers execute truly in parallel. Native subagents and Workflows also fan out concurrently (send multiple `Agent` calls in one message; a Workflow's `parallel`/`pipeline` runs its stages concurrently). Serial spawning is a manager error, not a bridge limit.

- When tasks are independent, spawn every non-interactive worker first, before reading any result, status, or captain report from any of them. Issue the start calls together in one batch whenever possible.
- Never await one worker's completion — or its captain report — before launching an independent sibling. Waiting between spawns silently serializes the fleet and wastes wall-clock time.
- After the full fleet is launched, supervise all runs together per the "Mandatory 10-Minute Direct Supervision" contract.
- Use one `start_visible_first_mate_codex_pool` when the parts share context and need coordination (the first mate fans out Codex-native subagents itself); spawn multiple root workers only for genuinely independent tasks.

## Worker Exhaustion Fallback (down the backend ladder)

When the active worker backend runs out (grok capped, agy buckets cooling, etc.), keep delegating — just move down the ladder (grok-4.5 → agy → Claude Sonnet subagents). Do not silently start doing all the implementation as the manager model; the point is still to route heavy/parallel work off the manager. The no-nesting / no-parking / flat-fallback rules below are backend-agnostic and apply to every fallback fleet ("Codex" in the detection triggers = the capped backend).

**Only the top-level Claude manager owns this switch.** The Codex→Sonnet decision is made once, at the captain level. A spawned worker (a Codex first mate, a Codex subagent, or a Sonnet fallback agent) that discovers Codex is capped MUST NOT decide to build its own fallback fleet — it stops and reports the cap upward, and the top-level manager reroutes. This is what prevents the nesting spiral: workers hitting the cap and each spinning up their own Sonnet sub-fleets.

**Detect Codex-out.** Treat Codex as unavailable when any of these hold:

- `codex` / `codex-reply` or a visible/interactive start tool returns a usage, quota, rate-limit, plan-cap, `429`, "usage limit reached", "insufficient quota", or "out of credits" error.
- Codex repeatedly fails to start or immediately exits with a usage/billing message.
- The user says Codex usage is out or asks to stop using Codex for cost/quota reasons.

Verify it is genuinely a usage problem, not a transient network blip or a one-off tool error, before switching. A single retryable error is not exhaustion; a clear quota/limit message or repeated usage failures is.

**Latch the cap once; do not let every worker rediscover it.** As soon as the manager confirms Codex is out, record it in `.claude-codex/BRIDGE.md` (e.g. `Codex: CAPPED until <reset date/time>`) and stop issuing Codex delegation for the rest of the session. Do not keep firing `codex` / visible-start calls per work item and letting each one fail into the cap — that is what produced the flood of failed delegations. If the cap has a known reset (e.g. usage returns July 10), note it and treat Codex as unavailable until then rather than retrying on every task.

**Fall back to Sonnet subagents.** Once Codex is confirmed out:

- Spawn Claude subagents with the `Agent` tool using `model: sonnet` for the worker roles Codex would have filled — exploration, first-pass implementation, mechanical refactors, test repair, and broad codebase reading.
- Map the Codex roles to Sonnet agent types: use the `Explore` agent (or `general-purpose` with a read-only brief) in place of `claude-explorer`, `general-purpose` in place of `claude-implementer`, and a review-focused `general-purpose`/`code-reviewer` brief in place of `claude-reviewer`.
- Keep the same manager discipline: Claude still owns architecture, decomposition, acceptance criteria, scope, and final review; Sonnet agents only execute the briefs. For file-disjoint parallel work, dispatch multiple Sonnet agents in one message so they run concurrently, one work item each.
- Reuse the same briefs, permission intent, and acceptance criteria you would have handed Codex. The routing target changes; the captain/worker split does not.
- Tell the user Codex usage is exhausted and that work is now running on Sonnet agents. Note that visible-terminal steering, `captain_report`, and the Codex-specific visible/first-mate harness do not apply to Sonnet agents; steer them through follow-up `Agent`/`SendMessage` briefs and review their returned results directly.

**Flat fallback — no nesting, no parking, no rogue-writer games.** The Sonnet fallback fleet is one flat layer of workers under the top-level manager. Enforce all of the following, and encode them into every fallback brief:

- **No re-delegation.** A Sonnet fallback agent executes its brief and returns a result. It must not itself try to "delegate to Codex," must not spawn further sub-agents, and must not invoke the claude-manages-codex routing. Only the top-level manager delegates. (Codex being capped means the whole "route to Codex" instruction is off for the session — say so in the brief so the worker does not try and fail.)
- **No parking.** Fallback agents run to completion and terminate with a result or a concrete blocker. They do not idle, wait for Codex to come back, or wait for a captain hand-off. The captain-help mailbox, `request_captain_help`, `submit_captain_report`, and "blocked_waiting_for_captain" are Codex visible-harness concepts and DO NOT apply to Agent-tool Sonnet workers — a blocked Sonnet agent returns its blocker text and stops.
- **No stand-down protocol between workers.** Fallback agents do not message each other, do not police the working tree for other writers, and do not invent "stand-down" or "rogue writer" handshakes. Coordination is the manager's job: give each parallel agent a file-disjoint scope up front so they never need to negotiate.
- **The user and the manager are not rogue writers.** Concurrent edits from the human owner or the Claude manager are expected and legitimate. An agent that sees files change under it must NOT label that a "rogue writer," stand down, or abort — it reports the unexpected change as an observation and continues within its own scope, and the manager reconciles. Only the top-level manager arbitrates real file-scope conflicts.

**Recover.** When Codex usage is restored (new billing window, user tops up, or the user asks to resume Codex), return to routing heavy/parallel work through Codex per the Routing Mandate. Sonnet-agent fallback is a stopgap, not the default fleet.

## Codex MCP Harness

Use the plugin-provided MCP server `codex-worker`.

The server exposes:

- `codex`: start a new Codex root worker session.
- `codex-reply`: continue a Codex root worker session with a `threadId`.

Important `codex` arguments:

- `prompt`: the worker brief.
- `cwd`: project directory.
- `sandbox`: `read-only`, `workspace-write`, or `danger-full-access`.
- `approval-policy`: use `never` unless the user explicitly wants interactive approvals.
- `developer-instructions`: use this to enforce Claude manager / Codex worker roles.
- `model`: set `gpt-5.6-sol`.
- `config`: include `model_reasoning_effort="<tier>"` where `<tier>` is the effort Claude selected for this task (`high`, `xhigh`, `max`, or `ultra`), and `service_tier="fast"`.

When a Codex response includes `structuredContent.threadId`, record it and use `codex-reply` for follow-up to that same root worker.

## Visible Agent Harness

Use the plugin-provided MCP server `agent-visibility` when the user wants to see what is happening or when work will take more than a quick turn.

(The preferred backends are windowless — native grok subagent / `start_claude_worker` — see "Worker Backends & Routing" above. **Codex is DISABLED**; the visible-Codex tools in this section remain documented only for a possible future revival — do not use them.)

The server exposes:

- `start_visible_codex_worker`: launches `codex exec --json` in a separate visible PowerShell window, saves the prompt and event logs, and returns a run directory.
- `start_visible_haiku_composed_codex_worker`: launches a visible run where Claude passes a compact `prompt_brief`, Haiku/low composes the full Codex prompt, then Codex executes it.
- `start_visible_first_mate_codex_pool`: launches a visible Codex root coordinator instructed to spawn and manage Codex subagents.
- `start_interactive_codex_tui` (**deprecated**): launches the real interactive Codex TUI in a visible terminal for an explicit hands-on user request, with bridge sidecar metadata but no structured JSONL event stream.
- `start_interactive_first_mate_codex_tui` (**deprecated**): launches the first-mate Codex coordinator in the real interactive Codex TUI only for an explicit hands-on user request.
- `steer_visible_codex_run`: sends a captain steering instruction to an existing visible Codex run. By default it interrupts an in-flight turn and resumes the same thread immediately; an idle worker consumes the queue without interruption. If the window already closed and a `thread_id` exists, it launches a visible resume run on that thread.
- `request_captain_help`: worker-side callback for a stuck visible Codex run to ask the same Claude captain for feedback.
- `list_captain_help_requests`: captain-side view of pending stuck-worker requests.
- `respond_to_captain_help_request`: captain-side response that records the answer and queues steering back to the same Codex run/thread.
- `submit_captain_report`: worker-side final report handoff for interactive TUI runs. It writes `captain_reports/final.json` and `final.md` so Claude receives the result even when the TUI closes.
- `list_captain_reports`: captain-side view of final reports from interactive TUI runs.
- `get_visible_run_status`: reads status and recent log lines from a visible run directory.
- `list_visible_runs`: lists recent visible runs.

Visible start tools force Codex to `gpt-5.6-sol` / `service_tier=fast` and honor the `reasoning_effort` Claude passes for the run, validated against `gpt-5.6-sol`'s accepted values (`minimal` / `low` / `medium` / `high` / `xhigh` / `max` / `ultra`; an unknown or missing value falls back to the `xhigh` default floor). Pass `reasoning_effort` on the start/pool/TUI tools to set the task's effort. The Haiku composer uses Claude `haiku` / `low` and a small default budget before Codex starts.

Use these optional arguments:

- `session_context`: compact current-session briefing for the spawned worker. Include the user goal, decisions already made, files touched, verification results, blockers, and any known mistakes to avoid.
- `resume_session_id`: Codex thread/session id from `get_visible_run_status.thread_id`, `list_visible_runs.thread_id`, or a prior Codex result. Use this when a visible Codex run was cut off or needs continuation.
- `requires_tool_access`: set `true` for SSH, live-device, serial, hardware, network, Docker, package-manager, or external-tool debugging.
- `compose_with_haiku`: optional on `start_visible_codex_worker`; set `true` when `prompt` is a compact brief rather than a final Codex prompt.
- `prompt_brief`: use this with `start_visible_haiku_composed_codex_worker`. Keep it short: objective, decisions, constraints, scope, verification, and non-goals.
- `steer_idle_seconds`: visible Codex runs wait briefly after each turn for queued steering, then close and reap child processes.
- `captain_help`: returned by visible start tools; points to the per-run same-captain help mailbox.
- `no_alt_screen`: interactive TUI tools can preserve scrollback when set to `true`.
- `close_on_exit`: interactive TUI tools close when the underlying TUI exits by default.
- `auto_close_after_report`: interactive TUI tools watch for `captain_reports/final.*` and close the terminal a few seconds after the report by default.

Use visible tools for:

- codebase-reading passes that should be observable
- first-mate worker pools
- long implementation or test-repair runs
- SSH, live-device, serial, hardware, network, Docker, package-manager, or external-tool debugging where Codex must run the same tools a developer would run
- any user request to see live work

Default to `start_visible_first_mate_codex_pool` for Claude-managed fan-out. For a single worker, default to `start_visible_haiku_composed_codex_worker` when Claude has a compact brief or `start_visible_codex_worker` when a final prompt already exists. These non-interactive visible CLI workers are the fully supported path for structured logs, direct steering, completion watchers, and captain-help.

Use direct `start_visible_codex_worker` for tiny prompts or whenever a final prompt already exists outside Claude output.

## Deprecated: Interactive TUI mode

`start_interactive_codex_tui` and `start_interactive_first_mate_codex_tui` remain available only when the user explicitly asks for a hands-on interactive Codex terminal; tell the user when choosing this deprecated path. TUI mode can flash-close, cannot accept programmatic bridge steering in an already-open terminal, and relies on the worker remembering `submit_captain_report` for captain handoff. It is not the fallback when routing is uncertain.

## Grok Worker Backend (added 2026-07-14; legacy visible-window path as of 2026-07-18)

Added because the owner's ChatGPT/Codex login was lost. The preferred default for grok-4.5 is now windowless — see "Worker Backends & Routing" above (native grok subagent, or `start_claude_worker`) and `references/legacy-backends.md` for a condensed summary. Use this grok-CLI path specifically when a task needs its CLI-only extras (Parallel Competition Mode, Mandatory Parallel Work-Checker — see below). Codex is untouched by this addition and remains a peer backend, currently disabled (see "Worker Backends & Routing" above and `check_worker_backends`).

The server exposes:

- `start_visible_grok_worker`: launches `grok --prompt-file <prompt.md> --output-format streaming-json --cwd <cwd> --permission-mode bypassPermissions -m grok-4.5 [--reasoning-effort low|medium|high] [-r <sessionId>]` in a separate visible PowerShell window, saves prompt/event logs, and returns a run directory. (`-p`/`--single` and `--prompt-file` are alternative ways to supply the prompt — confirmed live that combining them errors with `a value is required for '--single <PROMPT>'` — so the runner uses `--prompt-file` alone.) Every turn's answer is auto-written to `captain_reports/final.json` / `final.md` (Layer 1 callback, see "Worker Backends & Routing").
- `start_visible_haiku_composed_grok_worker`: Claude passes a compact `prompt_brief`; the Haiku/low composer expands it (the same composer flow the Codex path uses, including its non-fatal fallback to the raw brief on composer failure), then Grok executes the composed prompt.
- `start_visible_first_mate_grok_pool`: launches a single grok-4.5 process with its native subagent capability left enabled (no `--no-subagents`), using the same `_first_mate_prompt` brief as the Codex first-mate pool.
- `steer_visible_grok_run`: sends a captain steering instruction to an existing visible Grok run, mirroring `steer_visible_codex_run`. An idle worker consumes the queued instruction within a second; an active worker is interrupted best-effort (Ctrl+C/taskkill) when a launcher pid is known, then resumed with `grok -r <sessionId>`. Grok has no on-disk session-readiness probe like Codex's thread-file check, so after an interrupt this always launches the resume run directly on the last recorded session id — queued-at-idle delivery is the more reliable v1 path.
- Grok workers share the backend-agnostic read/report/help tools unchanged: `get_visible_run_status`, `list_visible_runs`, `submit_captain_report`, `list_captain_reports`, `request_captain_help`, `list_captain_help_requests`, `respond_to_captain_help_request` (see the callback-model limitation in "Worker Backends & Routing" for the live-MCP-callback caveat on `submit_captain_report` / `request_captain_help`).

### Grok effort caveat

`grok-4.5`'s `--reasoning-effort` CLI flag only accepts `low` / `medium` / `high` — `xhigh` and `max` are rejected outright ("unknown effort level"). Grok's own `~/.grok/config.toml` sets `default_reasoning_effort = "xhigh"`, which applies only when the flag is **omitted**. So the owner's desired default (grok-4.5 at xhigh) is reached by passing `reasoning_effort=""` (or anything outside low/medium/high) so the bridge's `_grok_effort_flag` omits the CLI flag entirely. Pass `reasoning_effort="high"` (etc.) only when a lower tier than the config default is deliberately wanted.

### Machine setup: `~/.grok/config.toml` MCP entry

To let a Grok worker reach the shared MCP tools (Layer 2 callback), the bridge added this to `~/.grok/config.toml` (backed up first to `config.toml.bak`, merged additively — the existing `[mcp_servers.kicad]` / `[mcp_servers.altium]` entries were preserved):

```toml
[mcp_servers.agent-visibility]
command = "C:/Users/jonny/AppData/Local/Python/pythoncore-3.14-64/python.exe"
args = ["C:/Users/jonny/.agent-bridge/visible_agent_bridge.py"]
enabled = true

[mcp_servers.agent-visibility.env]
```

This points at the **deployed** bridge copy (matching how Codex's own `agent-visibility` MCP wiring points at the deployed copy, not the dev repo), so it keeps working once the manager syncs this addition from `claude-manages-codex-bridge/` into `~/.agent-bridge/`.

## Antigravity / Gemini (agy) Worker Backend (added 2026-07-14; on-request, legacy visible-window path)

A peer backend alongside Codex and Grok — not a replacement for either, and not one of the two windowless default paths (see "Worker Backends & Routing" above and `references/legacy-backends.md` for a condensed summary). Use it only when the owner explicitly asks for Antigravity/Gemini (see "Default routing policy" above).

The server exposes:

- `start_visible_agy_worker`: launches `agy -p "<prompt>" --model "<model>" --dangerously-skip-permissions --add-dir <cwd>` (running with `cwd` set to the target directory) in a separate visible PowerShell window, saves prompt/output/display logs, and returns a run directory. Every turn's raw stdout is auto-written to `captain_reports/final.json` / `final.md` (Layer 1 callback — the ONLY callback path for agy, see "Callback model" above).
- `start_visible_haiku_composed_agy_worker`: Claude passes a compact `prompt_brief`; the Haiku/low composer expands it (the same composer flow the Codex/Grok paths use, including non-fatal fallback to the raw brief on composer failure), then agy executes the composed prompt.
- `steer_visible_agy_run`: sends a captain steering instruction to an existing visible agy run. An idle worker (in its steering window) consumes the queued instruction within a second, running `agy --continue` inside the SAME still-open window. A closed or interrupted run instead launches a brand-new `start_visible_agy_worker` run whose first turn is itself `agy --continue` (internal `resume_continue=True` knob) — this reaches the same underlying conversation only because `--continue` is cwd-scoped (see "No session id" below), not because any thread id is tracked. No first-mate pool tool is offered for agy (single worker only; the spec did not call for one).
- agy workers share the backend-agnostic read/report/help tools unchanged: `get_visible_run_status`, `list_visible_runs`, `submit_captain_report`, `list_captain_reports`, `request_captain_help`, `list_captain_help_requests`, `respond_to_captain_help_request` — the allowlist accepts `metadata.agent == "agy"`, but nothing in the agy worker's own prompt tells it to call them (see "Callback model" above), so these only matter if Claude calls them directly against an agy run directory.

### agy is plain text, not streaming JSON

Unlike Codex (`--json`) and Grok (`--output-format streaming-json`), `agy` has no structured event stream: `agy --help` exposes no `--output-format`/`--json`-style flag. The runner cannot parse `type: "text"/"end"/"error"` events the way the Codex/Grok runners do — it runs `agy` as one blocking call per turn, redirects stdout/stderr to separate temp files (`1> ... 2> ...`, not merged), appends the full stdout to `output.txt` + `display.log`, and writes `captain_reports/final.md`/`final.json` from that turn's **complete, unfiltered** stdout. stderr is logged to `display.log` only and never enters `output.txt` or the captain report. Because there is no incremental streaming, the visible window shows nothing new between "Starting Antigravity new/resume turn" and the turn's exit — this is expected, not a hang, for the turn durations observed live (single-digit seconds for a short prompt).

### agy effort is baked into the model name

`agy` has no `--reasoning-effort` flag at all. Effort is selected by picking a different `--model` value:

```
AGY_MODELS_BY_EFFORT = {"high": "Gemini 3.5 Flash (High)", "medium": "Gemini 3.5 Flash (Medium)", "low": "Gemini 3.5 Flash (Low)"}
AGY_DEFAULT_MODEL = "Gemini 3.5 Flash (High)"
```

`start_visible_agy_worker`'s `reasoning_effort` parameter (default `"high"`) is looked up in this table via `_agy_model_for_effort`; anything outside `low`/`medium`/`high` (case-insensitive) falls back to the `"high"` model. `agy models` also lists non-Gemini options (`Gemini 3.1 Pro (Low|High)`, `Claude Sonnet 4.6 (Thinking)`, `Claude Opus 4.6 (Thinking)`, `GPT-OSS 120B (Medium)`) that this bridge does not route to — the effort table only covers the three Gemini 3.5 Flash tiers the owner asked for.

### agy has no session id — `--continue` is cwd-scoped, not thread-scoped

`agy` never prints a session/conversation id on a plain-text turn. `agy --help` does expose `--conversation <id>` (resume a specific conversation) alongside `--continue`/`-c` (resume the **most recent** conversation for the current working directory), but with no id ever surfaced in stdout to capture, `--conversation <id>` is unusable from this bridge. Every resume in this backend therefore uses `--continue`, which is a **best-effort, cwd-scoped** resume: it reaches whatever agy conversation was most recently active in that directory, not a specific tracked thread. This is weaker than Grok's `-r <sessionId>` or Codex's thread-file resume — if another agy conversation is started in the same cwd between a run closing and a steer/resume call, `--continue` would pick up that other conversation instead. Verified live (2026-07-14): a `steer_visible_agy_run` call on a fully closed run correctly recalled the exact marker text from the original run's first turn after a `launched_resume` follow-up, confirming `--continue` does carry real context across process launches within a cwd, subject to the caveat above.

### Long-prompt inline handling

`agy` has no `--prompt-file` flag; the full prompt (including the permission contract and session-context bootstrap, when not using the Haiku composer) is passed inline as a single `-p` argument via PowerShell array splatting (`& $Agy @argsList`), the same mechanism Codex/Grok use for their own long arguments. This avoids `cmd.exe`'s 8191-character line limit (agy.exe is a real executable, not a `.cmd` shim), but very large prompts are still subject to the OS process-argument limit (Windows `CreateProcess` command-line cap, roughly 32K characters combined). Prefer `start_visible_haiku_composed_agy_worker` for large captain briefs, matching the existing Codex/Grok guidance.

## Active Steering Loop

Claude actively manages the default non-interactive visible Codex CLI runs instead of letting them drift. An explicitly requested deprecated TUI run is user-steered in the terminal and must be reviewed through its sidecar metadata/session artifacts plus `captain_report` afterward.

1. Start one non-interactive visible CLI root worker or first-mate pool with the goal, constraints, and acceptance criteria by default.
2. Poll with `get_visible_run_status`; read the tail, pending steer count, pending help requests, thread/session id, status, and `captain_report`.
3. At least every 10 minutes for long-running fleets, run an active supervision pass per the "Mandatory 10-Minute Direct Supervision" contract, not just a status poll: inspect recent actions/log tails/reports, check the captain-help mailbox, compare direction against Claude's architecture and acceptance criteria, decide whether the worker is on track, and steer drift immediately.
4. Periodically check up with active agents before they spiral: ask for a compact health/status checkpoint, current assumption, blocker, next action, and expected verification. Use short steering notes; do not wait for obvious failure if output quality is drifting, confused, or bug-prone.
5. If `pending_help_requests` is nonzero, read `help_requests` or call `list_captain_help_requests`, then answer with `respond_to_captain_help_request`.
6. When Codex needs correction, narrowing, extra context, changed priorities, or a review checkpoint, call `steer_visible_codex_run` with a short captain instruction and the same run directory; delivery is direct by default (see step 9), not queued behind the current turn. For a deprecated TUI run, steer directly in the terminal or resume the saved session; bridge steering does not type into the open TUI.
7. When multiple agents converge on the same root cause or design decision from different directions, consolidate it into one canonical world model and steer every active run to that model. Do not let stale assumptions keep running in parallel.
8. If the worker is right to escalate, ask the user the specific decision question yourself, then call `respond_to_captain_help_request` with the user's answer. Do not tell Codex to ask the user directly.
9. Steering is direct by default: `steer_visible_codex_run` interrupts an in-flight turn and resumes the same thread immediately with the captain instruction, so corrections land now instead of after the current turn finishes. Workers idle in their steering window consume the queue within a second and are never interrupted. Pass `interrupt_current_turn: false` to wait for the turn boundary only when the guidance is non-urgent and preserving the in-flight turn's partial work matters more than latency. Prefer steering an existing thread over starting a new run either way.
10. If Claude changes permission intent mid-session, pass `sandbox: workspace-write` or `sandbox: danger-full-access` in the steering call so Codex receives an updated permission contract.
11. If the default non-interactive visible window closed, let `steer_visible_codex_run` or `respond_to_captain_help_request` launch a visible resume run on the same thread. Start fresh only for unrelated work or polluted context. Resume an explicitly requested deprecated TUI with its TUI start tool and saved session id when available.
12. For a deprecated TUI run, treat terminal text as user-visible progress only; the captain-facing outcome is the `submit_captain_report` artifact. Non-interactive workers report through their structured run artifacts.

Keep steering notes short. State the decision, changed scope, files or tests to focus on, and required next response shape. Do not restate the whole task unless the thread lost context.

Use invisible `codex` / `codex-reply` for quick, low-noise, manager-controlled exchanges where live observation is not needed.

## Mandatory 10-Minute Direct Supervision

While any default non-interactive Codex worker or fleet is active, Claude runs a direct supervision pass at least every 10 minutes. The same cadence applies to an explicitly requested deprecated TUI session. This is supervision and review of the work itself, not a liveness probe: confirming the process is still running, or reading only the `status` field, does not count as a pass.

Every pass must do all of the following:

1. Read the worker's actual recent work from the `get_visible_run_status` tail and structured run artifacts — commands run, files touched, stated reasoning, and output produced since the last pass. For a deprecated TUI run, read `captain_report` / `list_captain_reports` and its sidecar artifacts.
2. Check the captain-help mailbox and the pending steer queue.
3. Render an explicit on-track / off-track verdict against Claude's stated architecture, acceptance criteria, and permission contract. Record the verdict in the bridge ledger for long-running fleets.
4. Act on the verdict immediately. If off-track, drifting, or approaching an expensive or irreversible step: send a short captain correction through `steer_visible_codex_run` that quotes or names the specific reviewed output it is correcting. For a deprecated TUI run, use terminal steering or session resume. If on-track: say so in the ledger, and request a compact checkpoint (current assumption, blocker, next action, expected verification) whenever the next milestone is unclear.
5. Note when the next pass is due (10 minutes or less) before returning to other work.

A steer issued without first reading the recent work is not supervision, and a read without a verdict is not review. If two consecutive passes are missed, treat it as a supervision failure: stop launching new delegation, re-read the full ledger and each active run's recent output, and re-establish verdicts before continuing.

## Completion Watcher Contract

The bridge never wakes Claude when a Codex run finishes: start tools are fire-and-forget, and an idle Claude turn is never re-invoked by the MCP server. Without a watcher, a finished worker sits unnoticed while Claude "waits" forever.

- Immediately after every default non-interactive spawn or resume — single worker, pool, or steer follow-up — arm the `watch_command` returned by the start tool as a background Bash task (`run_in_background: true`). The command exits the moment the run reaches a terminal state, which wakes Claude with a completion notification. An explicitly requested deprecated TUI also returns a watcher that terminates on closure or a captain report.
- Never end a turn waiting for Codex without a watcher armed on every active run.
- Watchers detect completion; they do not replace the 10-minute direct supervision passes, which review direction while the run is still working.
- On wake, read the run's `captain_report` / status and continue: review the result, steer, or report to the user. Do not re-arm a watcher on a run that already reached a terminal state.

## Codex Run Ownership and Subagent Handoff

Every Codex run has exactly one owner: the main Claude manager loop. Ephemeral Claude subagents die with their task, and any watcher or supervision duty they held dies with them — a Codex run started inside a subagent and left running when the subagent returns is an orphan nobody will ever check on.

- Do not spawn Codex runs from ephemeral Claude subagents. The Routing Mandate already routes fan-out through Codex itself: when Codex work is needed, the manager spawns it directly and arms the watcher in its own loop.
- A subagent that must start a Codex run anyway has exactly two valid exits: (1) stay alive until the run reaches a terminal state and fold the outcome into its final report, or (2) hand the run off — its final message must list every run it started under a "Codex runs handed off" heading with `run_dir`, `thread_id`, current status, and `watch_command` so the main loop can adopt them.
- The manager adopts handed-off runs immediately, before any other work: arm each `watch_command` as a background task, record the run in the bridge ledger, and fold it into the 10-minute supervision rotation.
- Safety sweep: after any Claude subagent returns — and at the start of any session that may have inherited work — call `list_visible_runs` on the working repo and adopt every run still in a non-terminal status. An active run with no owner is a supervision failure to fix on the spot.

## Same-Captain Help Callback

Visible Codex prompts include a run-specific captain-help callback. When a spawned worker is blocked, confused, sees conflicting evidence, lacks confidence for `workspace-write`, or needs user-level approval, it should call `request_captain_help` with the visible `run_dir`, then stop its current turn with `Outcome: blocked_waiting_for_captain`.

Claude owns the response:

- use `get_visible_run_status` or `list_captain_help_requests` to inspect the request
- answer with `respond_to_captain_help_request` when Claude can decide
- ask the user a focused question when the request needs owner judgment, credentials, destructive permission, product direction, or risk acceptance
- after the user answers, send the decision back with `respond_to_captain_help_request`
- for a deprecated interactive TUI run, expect the answer to be a recorded mailbox artifact; direct terminal steering or a resumed TUI may still be needed because queued steering cannot type into an already-open TUI

Do not route same-captain help through `start_visible_claude_advisor` unless Claude explicitly wants a separate one-shot advisor. The point of the callback is to keep the spawned worker connected to the captain that launched it.

## Codex Subagents

Codex only spawns subagents when explicitly asked. Claude must be explicit.

Available built-in Codex agents:

- `explorer`: read-heavy codebase exploration.
- `worker`: implementation and fixes.
- `default`: general fallback.

Personal custom Codex agents installed for this bridge:

- `claude-explorer`: no-edit, low-cost scouting, Python-backed skill use, and context distillation.
- `claude-implementer`: bounded implementation under Claude's scope.
- `claude-reviewer`: no-edit correctness/security/regression review.
- `claude-debugger`: full-tool SSH, live-device, network, serial, and command-heavy debugging after Claude explicitly allows full tool access.

Use subagents for independent, noisy, read-heavy, or parallelizable work. Avoid subagents for tiny edits or where the coordination overhead exceeds the benefit.

## First Mate Pattern

When a task requires codebase understanding, do not spend Claude tokens reading everything. Start a visible first-mate pool or a no-edit Codex root session and tell Codex to map the repo for Claude.

The bridge bundles a Codex-facing Firstmate skill at `codex-skills/firstmate/SKILL.md`. Install or sync it to `~/.codex/skills/firstmate/SKILL.md` when using this repo locally. The visible first-mate runner also embeds the same role contract so the hierarchy works even before Codex refreshes its skill index.

Default first-mate settings:

- model: `gpt-5.6-sol`
- reasoning effort: Claude-selected per task (`high` / `xhigh` / `max` / `ultra`); defaults to the `xhigh` floor when unset
- service tier: `fast`
- process sandbox: full tool access by default so Python skills and external tooling work
- permission intent: `read-only`/no-edit for codebase mapping, `workspace-write` only after Claude chooses a scoped implementation path, `danger-full-access` or `requires_tool_access: true` for SSH/live-device/tool debugging
- max worker fan-out: 6 unless the task is clearly smaller

First-mate responsibilities:

- spawn `claude-explorer` subagents for independent codebase areas
- summarize architecture, key files, tests, data flow, risks, and likely edit points
- update `.claude-codex/BRIDGE.md`
- return a compact manager brief for Claude
- avoid dumping raw logs or large code excerpts into Claude's context

For broad codebase understanding, ask:

```text
Use the firstmate skill. Claude is the captain; Codex is the first mate. Spawn claude-explorer subagents to map the codebase by subsystem. Do not edit files. Return a compact manager brief with architecture, key files, tests, risk areas, and recommended implementation plan.
```

## Session Context and Resume

Do not treat spawned Codex as a blank chat.

Before starting or resuming Codex:

1. Build a compact `session_context` from the live Claude conversation: user goal, decisions, constraints, prior errors, run ids, thread ids, changed files, verification, and open questions.
2. If context predates the current Claude window or was compacted, invoke `read-past-sessions` or tell Codex to use it immediately.
3. When the worker needs broad project/codebase context, tell Codex to use read-past-sessions' Graphify memory flow before brute-force file reading: try `memory-query`; if no graph exists, build/refresh the curated corpus with `memory-corpus` plus `memory-codex --build-graph` when Codex CLI is authenticated, or `memory-graph` as deterministic fallback.
4. Pass `session_context` into the non-interactive visible CLI start or pool tool by default. Pass it into a TUI start tool only for an explicitly requested deprecated interactive run.
5. If continuing previous work, pass `resume_session_id` instead of starting a new root run. For Codex this is the `thread_id` shown by `get_visible_run_status` or `list_visible_runs`.
6. For an already-running visible worker, call `steer_visible_codex_run` instead of starting another root session.
7. Record resumable ids in `.claude-codex/BRIDGE.md`.

Use a fresh Codex session only for unrelated work or when the old session is polluted.

## Permission Policy

Default the permission intent to `read-only`/no-edit unless Claude is fully confident the work is well-scoped and safe. The actual visible Codex process still has full tool access so Python skills and developer tooling work.

Use `workspace-write` only when all are true:

- Claude has chosen the implementation direction.
- Target files or ownership boundaries are clear.
- The task is not destructive, broad, security-sensitive, or data-loss-prone.
- Parallel writers will not touch the same files.

If not fully confident, use no-edit intent and ask Codex to return findings, risks, and questions. Claude decides next.

Use `danger-full-access` intent only when the user or Claude explicitly authorizes broad/full tool work. This bridge has user authorization to support full-tool Codex debugging; do not cripple Codex with a literal read-only process sandbox, because that breaks Python and skills.

Subagents inherit the parent Codex process access unless a custom agent overrides it. Start the root Codex session with the intended permission intent. Use `claude-debugger` for full-tool subagent tasks.

## Delegation Patterns

### No-Edit Scout

Use when Claude needs context before deciding.

Start Codex with no-edit permission intent through `start_visible_first_mate_codex_pool`, and tell it:

```text
Spawn claude-explorer subagents for the independent areas below. Wait for all agents, then return a consolidated summary only.

Areas:
1. <area A>
2. <area B>

For each result include: relevant files, current behavior, risks, and unanswered questions. Do not edit files.
```

### Bounded Implementation

Use when Claude is confident enough to permit writes.

Start or resume Codex with `sandbox: workspace-write` through `start_visible_first_mate_codex_pool` for fan-out, `start_visible_haiku_composed_codex_worker` for a compact single-worker brief, or `start_visible_codex_worker` for a final prompt, and tell it:

```text
Claude has chosen the implementation path. Use one claude-implementer subagent unless the listed work items are file-disjoint.

Scope:
- Goal: <goal>
- Files/areas: <paths>
- Non-goals: <what not to touch>
- Acceptance criteria: <criteria>
- Verification: <commands>

Do not change architecture. If the scope is ambiguous, stop and ask Claude.
```

### Live Debugging, SSH, and Tool Access

Use when Codex must run real developer tools, SSH to a device, inspect network state, use serial tooling, run package managers, or debug hardware/runtime behavior.

Start or resume Codex with `requires_tool_access: true` and include the previous `resume_session_id` when continuing the same run. Tell it:

```text
Claude explicitly authorizes full tool access for this debugging scope.
Use claude-debugger for SSH/live-device/tool-heavy work. Start with read-only inspection commands, report commands and results, and ask Claude before destructive actions, service restarts, credential changes, data deletion, firmware flashing, or persistent system changes.

Scope:
- Target: <host/device/repo>
- Goal: <observable issue>
- Allowed commands/tools: <ssh/tests/logs/etc.>
- Forbidden actions: <destructive or persistent actions>
- Verification: <what proves the issue is fixed>
```

If an older Codex thread was created before the full-tool default and still cannot access Python/tools after resume, start a fresh full-tool worker and pass the old thread id in `session_context`.

### Parallel Implementation

Use only for file-disjoint work.

Tell Codex exactly how to split work:

```text
Spawn exactly N claude-implementer subagents, one per work item. These work items are file-disjoint. Each subagent may edit only its assigned files. Wait for all agents, resolve non-overlapping results, and return changed files plus verification.
```

If file ownership is not clear, do not parallelize writes.

### Review Pass

After a non-trivial diff, use a no-edit Codex review or Claude's own review.

```text
Spawn one claude-reviewer subagent. Review the current diff against Claude's stated architecture and acceptance criteria. Do not edit files. Findings first, ordered by severity, with file references. If no issues, say so and list residual risk.
```

## Token Efficiency

- For non-trivial single-worker Codex delegation, Claude writes a compact captain brief and calls `start_visible_haiku_composed_codex_worker`; Haiku/low writes the long worker prompt.
- For fan-out, Claude calls `start_visible_first_mate_codex_pool`; when a final single-worker prompt already exists, Claude calls `start_visible_codex_worker` directly.
- Keep the Claude-authored `prompt_brief` to decisions and constraints: goal, scope, permission intent, files/areas, non-goals, verification, and open questions.
- Do not have Claude restate standard bridge rules, full task templates, or long worker checklists; the bridge and Haiku composer add those.
- Send Codex distilled briefs, not the whole Claude transcript.
- Include enough session context that Codex does not repeat already-fixed mistakes. For very long history, instruct Codex to use `read-past-sessions` and return a compact briefing before implementation.
- For broad project context, ask Codex to query the read-past-sessions Graphify memory graph before reading many source files; build the curated memory graph only when the existing graph is missing or stale.
- Ask Codex to read and summarize the codebase before Claude reads files directly.
- Use non-interactive visible first-mate pools for broad understanding instead of loading file after file into Claude.
- Put noisy exploration, logs, and test repair inside Codex subagents.
- Ask Codex to return summaries, changed files, verification results, blockers, and questions.
- Avoid making Claude read raw logs unless Codex cannot summarize them reliably.
- Reuse a root Codex `threadId` when follow-up context matters.
- Start fresh root sessions for unrelated work to avoid context pollution.
- Prefer `claude-explorer` for cheap parallel scans before spending Claude tokens on design decisions.
- Do not ask Codex to consult Claude unless the decision is high-value or uncertain.
- Keep subagent fan-out bounded. Codex defaults are designed for shallow delegation; do not request recursive subagent spawning.

## Visibility Standard

When launching visible work:

1. Tell the user a non-interactive visible Codex CLI worker or pool is opening. If the user explicitly requested the deprecated hands-on TUI path, say that instead.
2. Include the run directory in the bridge ledger.
3. Use `get_visible_run_status` for concise progress checks instead of reading raw JSONL.
4. Use `steer_visible_codex_run` to redirect the default non-interactive worker directly. An explicitly requested deprecated TUI must be steered by the user in the terminal or resumed later.
5. For a deprecated TUI run, read `captain_report` from `get_visible_run_status` or call `list_captain_reports`; terminal-only final text is not the captain handoff. For non-interactive workers, read the structured run status and logs.
6. Expect the visible terminal to show prompts, messages, commands, token usage, and diff summaries.
7. Do not promise hidden thoughts. Say "progress, reasoning summaries, commands, and implementation state" instead.

## Bridge Ledger

For non-trivial multi-agent work, use `.claude-codex/BRIDGE.md` in the repository root.

If the file does not exist, create:

```markdown
# Claude-Codex Bridge

## Goal

## Architecture Decisions

## Worker Ledger

| Worker | Thread ID | Sandbox | Scope | Status | Next Action |
| --- | --- | --- | --- | --- | --- |

## Visible Runs

| Run | Directory | Purpose | Status |
| --- | --- | --- | --- |

## Changed Files

## Open Questions

## Verification
```

Keep it concise. Record:

- Claude decisions
- Codex root `threadId`s
- subagent plan and ownership
- file scopes
- verification status
- blockers and next actions

Do not paste full transcripts.

## Claude Review Standard

Before final response, Claude independently checks:

- diff scope matches the user request
- implementation follows Claude's architecture
- parallel workers did not conflict
- verification was run where feasible
- no unrelated files or metadata changed
- no destructive or broad-permission action was taken without user approval

If the result is wrong, use `steer_visible_codex_run` for visible runs or `codex-reply` for invisible runs with a specific repair instruction. Do not ask Codex to review itself as the only validation step.
