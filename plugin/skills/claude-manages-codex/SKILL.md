---
name: claude-manages-codex
description: Use when Claude Code should act as project manager, first mate, architect, and reviewer while delegating implementation, exploration, Codex subagent orchestration, codebase reading, mechanical refactors, test repair, or cheap iteration to OpenAI Codex through the bundled codex-worker and visible agent MCP servers. Trigger for requests like "have Claude manage Codex", "delegate this to Codex", "use Codex as the worker", "parallelize with Codex", "ask Codex to implement", "use Codex subagents", "show visible worker logs", "first mate", or any coding task where Claude should make high-level decisions and Codex should do low-level work.
---

# claude-manages-codex

Use Claude as manager, first mate, architect, and reviewer. Use Codex as the worker harness, including Codex root sessions and Codex subagents.

## Core Model

- Claude owns architecture, task decomposition, acceptance criteria, risk calls, worker assignment, and final review.
- Codex owns cheap exploration, first-pass implementation, test repair, mechanical refactors, and noisy command/log work.
- Codex subagents are controlled through the Codex root session. Claude starts or resumes the root session with `codex` / `codex-reply`, then explicitly tells Codex when and how to spawn subagents.
- Claude must review Codex output and local diffs before claiming completion.
- Prefer Codex MCP over manual copy/paste.
- Prefer visible workers when the user wants to observe progress. Visible workers show prompts, streamed events, agent messages, commands, token usage, and diffs in a separate terminal plus logs under `.claude-codex/runs/`.
- Hidden model reasoning is not displayable. Surface useful progress, summaries, commands, and implementation state instead.

## Routing Mandate: Parallel Agents and Heavy Work → Codex

**Default rule: while this skill is active, Claude does not spawn its own parallel subagents and does not do heavy implementation directly. That work routes through Codex to preserve Claude tokens.** This overrides the default dispatch behavior of other skills and tools.

**Always route to Codex** — start or resume a Codex root session, then have it spawn `claude-explorer` / `claude-implementer` / `claude-reviewer` subagents:

- **Any parallel agent fan-out another skill or tool would trigger** — e.g. `dispatching-parallel-agents`, `subagent-driven-development`, `feature-dev`, the `Explore` / `Plan` agents, or any direct `Agent` / Task-tool subagent dispatch. Do not spawn Claude subagents for the fan-out; have Codex spawn its subagents instead.
- **Heavy coding work** — multi-file implementation, mechanical or large refactors, test repair, broad codebase reading, and noisy command/log iteration.

**Honor the other skill's discipline, delegate its execution.** When a process skill applies (TDD, systematic-debugging, executing-plans), Claude still follows that skill's method and checklist — but the actual fan-out and edits are carried out by Codex subagents, with the brief encoding the required discipline (e.g. "write the failing test first, then implement"). Claude decomposes, writes the briefs, and reviews; Codex executes.

**Claude keeps (never route):** architecture, task decomposition, acceptance criteria, risk and security calls, final review of every Codex diff, and the user-facing response.

**Do NOT route to Codex when:**

- The edit is tiny (single file, a few lines) where Codex coordination overhead exceeds the token savings — Claude just does it.
- The work needs tools or context only Claude can reach (MCP servers Codex lacks, this session's live state).
- The Codex bridge is unavailable or erroring — fall back to Claude and tell the user.
- The user explicitly asks Claude to do the work directly.

When routing, prefer a **visible** Codex run (`start_visible_first_mate_codex_pool` for fan-out, `start_visible_codex_worker` for a single worker) so the user can watch the token-saving work happen; use invisible `codex` / `codex-reply` only for quick, low-noise exchanges.

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
- `model`: omit unless the user or task requires a specific Codex model.
- `config`: use only for known Codex config overrides.

When a Codex response includes `structuredContent.threadId`, record it and use `codex-reply` for follow-up to that same root worker.

## Visible Agent Harness

Use the plugin-provided MCP server `agent-visibility` when the user wants to see what is happening or when work will take more than a quick turn.

The server exposes:

- `start_visible_codex_worker`: launches `codex exec --json` in a separate visible PowerShell window, saves the prompt and event logs, and returns a run directory.
- `start_visible_first_mate_codex_pool`: launches a visible Codex root coordinator instructed to spawn and manage Codex subagents.
- `get_visible_run_status`: reads status and recent log lines from a visible run directory.
- `list_visible_runs`: lists recent visible runs.

Use visible tools for:

- codebase-reading passes that should be observable
- first-mate worker pools
- long implementation or test-repair runs
- any user request to see live work

Use invisible `codex` / `codex-reply` for quick, low-noise, manager-controlled exchanges where live observation is not needed.

## Codex Subagents

Codex only spawns subagents when explicitly asked. Claude must be explicit.

Available built-in Codex agents:

- `explorer`: read-heavy codebase exploration.
- `worker`: implementation and fixes.
- `default`: general fallback.

Personal custom Codex agents installed for this bridge:

- `claude-explorer`: read-only, low-cost scouting and context distillation.
- `claude-implementer`: bounded implementation under Claude's scope.
- `claude-reviewer`: read-only correctness/security/regression review.

Use subagents for independent, noisy, read-heavy, or parallelizable work. Avoid subagents for tiny edits or where the coordination overhead exceeds the benefit.

## First Mate Pattern

When a task requires codebase understanding, do not spend Claude tokens reading everything. Start a visible first-mate pool or a read-only Codex root session and tell Codex to map the repo for Claude.

Default first-mate settings:

- model: `gpt-5.5`
- reasoning effort: `xhigh`
- root sandbox: `read-only` for codebase mapping, `workspace-write` only after Claude chooses a scoped implementation path
- max worker fan-out: 6 unless the task is clearly smaller

First-mate responsibilities:

- spawn `claude-explorer` subagents for independent codebase areas
- summarize architecture, key files, tests, data flow, risks, and likely edit points
- update `.claude-codex/BRIDGE.md`
- return a compact manager brief for Claude
- avoid dumping raw logs or large code excerpts into Claude's context

For broad codebase understanding, ask:

```text
Act as Codex First Mate for Claude. Spawn claude-explorer subagents to map the codebase by subsystem. Do not edit files. Return a compact manager brief with architecture, key files, tests, risk areas, and recommended implementation plan.
```

## Permission Policy

Default to `read-only` unless Claude is fully confident the work is well-scoped and safe.

Use `workspace-write` only when all are true:

- Claude has chosen the implementation direction.
- Target files or ownership boundaries are clear.
- The task is not destructive, broad, security-sensitive, or data-loss-prone.
- Parallel writers will not touch the same files.

If not fully confident, use `read-only` and ask Codex to return findings, risks, and questions. Claude decides next.

Never use `danger-full-access` unless the user explicitly asks and the environment is controlled.

Subagents inherit the parent Codex sandbox unless a custom agent overrides it. Start the root Codex session with the intended maximum permission.

## Delegation Patterns

### Read-Only Scout

Use when Claude needs context before deciding.

Start Codex with `sandbox: read-only`, or use `start_visible_first_mate_codex_pool`, and tell it:

```text
Spawn claude-explorer subagents for the independent areas below. Wait for all agents, then return a consolidated summary only.

Areas:
1. <area A>
2. <area B>

For each result include: relevant files, current behavior, risks, and unanswered questions. Do not edit files.
```

### Bounded Implementation

Use when Claude is confident enough to permit writes.

Start or resume Codex with `sandbox: workspace-write`, or use `start_visible_codex_worker`, and tell it:

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

### Parallel Implementation

Use only for file-disjoint work.

Tell Codex exactly how to split work:

```text
Spawn exactly N claude-implementer subagents, one per work item. These work items are file-disjoint. Each subagent may edit only its assigned files. Wait for all agents, resolve non-overlapping results, and return changed files plus verification.
```

If file ownership is not clear, do not parallelize writes.

### Review Pass

After a non-trivial diff, use a read-only Codex review or Claude's own review.

```text
Spawn one claude-reviewer subagent. Review the current diff against Claude's stated architecture and acceptance criteria. Do not edit files. Findings first, ordered by severity, with file references. If no issues, say so and list residual risk.
```

## Token Efficiency

- Send Codex distilled briefs, not the whole Claude transcript.
- Ask Codex to read and summarize the codebase before Claude reads files directly.
- Use visible first-mate pools for broad understanding instead of loading file after file into Claude.
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

1. Tell the user a visible terminal window is opening.
2. Include the run directory in the bridge ledger.
3. Use `get_visible_run_status` for concise progress checks instead of reading raw JSONL.
4. Expect the visible terminal to show prompts, messages, commands, token usage, and diff summaries.
5. Do not promise hidden thoughts. Say "progress, reasoning summaries, commands, and implementation state" instead.

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

If the result is wrong, use `codex-reply` with a specific repair instruction. Do not ask Codex to review itself as the only validation step.
