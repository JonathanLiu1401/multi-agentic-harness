# Interactive Codex TUI Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bridge tool that launches the real interactive Codex TUI in a visible terminal while recording sidecar metadata for Claude management and review.

**Architecture:** Keep the existing `codex exec --json` path unchanged. Add a separate `start_interactive_codex_tui` MCP tool backed by a focused TUI runner script, a TUI command builder, and best-effort session-id discovery. The TUI mode is user-steered and lower-fidelity than JSON exec mode; Claude reads sidecar files, Codex session artifacts, git diff, and tests after the user exits or resumes the TUI.

**Tech Stack:** Python 3.14, FastMCP, PowerShell, Codex CLI, existing script-style E2E harness in `tests/e2e_visible_bridge.py`.

## Global Constraints

- Do not replace or regress `start_visible_codex_worker`, `start_visible_haiku_composed_codex_worker`, `start_visible_first_mate_codex_pool`, or `steer_visible_codex_run`.
- The new TUI path must use top-level interactive `codex`, not `codex exec --json`.
- The new TUI path must force `gpt-5.6-sol` and `service_tier=fast`, and honor the per-run `reasoning_effort` (`high` / `xhigh` / `max` / `ultracode`, default `xhigh`).
- The new TUI path defaults to `approval_policy="on-request"` so the user can approve or reject directly in the TUI.
- Do not promise structured JSON event logs for TUI mode.
- Do not promise Claude can inject live text into the interactive TUI.
- Keep hidden model reasoning hidden; expose normal TUI output, metadata, summaries, commands, diffs, and saved artifacts only.
- Use `C:\Users\jonny\AppData\Roaming\npm\codex.cmd` through the existing `CODEX` constant.
- Preserve the current bridge permission model: full process/tool access where needed, with requested sandbox recorded as permission intent.
- Document reload boundaries after syncing live MCP files.

---

## File Structure

- Modify `visible_agent_bridge.py`
  - Add TUI constants and small helpers near existing launcher helpers.
  - Add `_codex_tui_args(...)` as a pure command construction unit.
  - Add `_interactive_codex_tui_runner(...)` as the PowerShell script generator.
  - Add `_find_recent_codex_session_id(...)` and `_record_interactive_session_id(...)` as best-effort sidecar helpers.
  - Add MCP tool `start_interactive_codex_tui(...)`.
  - Extend `get_visible_run_status(...)` and `list_visible_runs(...)` to report `mode` and best-effort `session_id`.
- Modify `tests/e2e_visible_bridge.py`
  - Add a no-launch dry-run case that monkeypatches `bridge._launch`.
  - Assert sidecar files, metadata, command script content, forced model settings, approval policy, and list/status visibility.
- Modify `README.md`
  - Add the tool to the exposed tools list, current behavior, usage guidance, E2E notes, and permission allowlist example.
- Modify `plugin/skills/claude-manages-codex/SKILL.md`
  - Add TUI mode to the visible harness section and routing guidance.
  - Clarify that Claude should use TUI mode when the user wants direct steering.
- Modify `C:\Users\jonny\.claude\settings.json` during rollout
  - Add the new allowlist entry.
- Sync generated/live files during rollout
  - Copy `visible_agent_bridge.py` to `C:\Users\jonny\.agent-bridge\visible_agent_bridge.py`.
  - Copy the Claude skill to `C:\Users\jonny\.claude\skills\claude-manages-codex\skills\claude-manages-codex\SKILL.md`.

---

### Task 1: Add No-Launch TUI Sidecar Test

**Files:**
- Modify: `tests/e2e_visible_bridge.py`

**Interfaces:**
- Consumes: future `bridge.start_interactive_codex_tui(...) -> dict[str, Any]`.
- Produces: failing test case `case_interactive_tui_sidecar_dry_run() -> dict[str, Any]` used by `main()`.

- [ ] **Step 1: Add the failing dry-run case**

Insert this function after `case_captain_help_mailbox()`:

```python
def case_interactive_tui_sidecar_dry_run() -> dict[str, Any]:
    original_launch = bridge._launch
    launched_scripts: list[Path] = []

    def fake_launch(script_path: Path) -> int:
        launched_scripts.append(script_path)
        return 424242

    try:
        bridge._launch = fake_launch  # type: ignore[assignment]
        result = bridge.start_interactive_codex_tui(
            prompt="Self-contained interactive TUI dry-run. Do not edit files.",
            cwd=str(ROOT),
            title="E2E interactive Codex TUI dry-run",
            sandbox="read-only",
            approval_policy="on-request",
            session_context=SESSION_CONTEXT,
            no_alt_screen=True,
            close_on_exit=False,
        )
    finally:
        bridge._launch = original_launch  # type: ignore[assignment]

    assert result["ok"], result
    assert result["pid"] == 424242, result
    assert launched_scripts, result

    run_dir = _run_dir(result)
    script = launched_scripts[0].read_text(encoding="utf-8-sig")
    metadata = _read_json(run_dir / "metadata.json", {})
    status = _read_json(run_dir / "status.json", {})

    assert metadata["agent"] == "codex", metadata
    assert metadata["mode"] == "interactive_tui", metadata
    assert metadata["model"] == bridge.CODEX_MODEL, metadata
    assert metadata["reasoning_effort"] == bridge.CODEX_REASONING_EFFORT, metadata
    assert metadata["service_tier"] == bridge.CODEX_SERVICE_TIER, metadata
    assert metadata["requested_sandbox"] == "read-only", metadata
    assert metadata["approval_policy"] == "on-request", metadata
    assert metadata["session_context_supplied"] is True, metadata
    assert status["status"] == "launched", status

    assert "codex.cmd" in script, script
    assert "'-m'" in script and "'gpt-5.6-sol'" in script, script
    assert "'-a'" in script and "'on-request'" in script, script
    assert "model_reasoning_effort=`\"xhigh`\"" in script, script
    assert "service_tier=`\"fast`\"" in script, script
    assert "--no-alt-screen" in script, script
    assert "--json" not in script, script
    assert "exec" not in script.split("$argsList", 1)[1].split("Write-Log", 1)[0], script

    assert (run_dir / "prompt.md").exists(), run_dir
    assert (run_dir / "session_context.md").exists(), run_dir
    assert (run_dir / "notes.md").exists(), run_dir
    assert (run_dir / "display.log").exists(), run_dir

    status_result = bridge.get_visible_run_status(str(run_dir), tail_lines=20)
    assert status_result["metadata"]["mode"] == "interactive_tui", status_result
    assert status_result["session_id"] is None, status_result

    listed = bridge.list_visible_runs(str(ROOT), limit=5)
    assert any(item["run_dir"] == str(run_dir) and item["metadata"].get("mode") == "interactive_tui" for item in listed), listed
    return {"run_dir": str(run_dir), "script": str(launched_scripts[0])}
```

- [ ] **Step 2: Wire the case into `main()`**

Change the printed count and insert the new case after captain help:

```python
print("[0/8] advisor model policy", flush=True)
_assert_model_policy()

print("[1/8] captain help mailbox", flush=True)
results["captain_help"] = case_captain_help_mailbox()
print(json.dumps(results["captain_help"], indent=2), flush=True)

print("[2/8] interactive TUI sidecar dry-run", flush=True)
results["interactive_tui"] = case_interactive_tui_sidecar_dry_run()
print(json.dumps(results["interactive_tui"], indent=2), flush=True)

print("[3/8] visible worker + queued steer", flush=True)
```

Then renumber the remaining printed labels through `[8/8] Claude advisor visible run`.

- [ ] **Step 3: Run the test and verify it fails for the right reason**

Run:

```powershell
python .\tests\e2e_visible_bridge.py --skip-expensive
```

Expected: FAIL with an `AttributeError` similar to:

```text
module 'visible_agent_bridge' has no attribute 'start_interactive_codex_tui'
```

- [ ] **Step 4: Commit the failing test if using multi-commit TDD**

```powershell
git add tests\e2e_visible_bridge.py
git commit -m "test(bridge): cover interactive codex tui sidecar"
```

If batching commits, leave the failing test uncommitted until Task 3 passes.

---

### Task 2: Implement TUI Command Builder and Runner

**Files:**
- Modify: `visible_agent_bridge.py`

**Interfaces:**
- Produces: `_codex_tui_args(...) -> list[str]`.
- Produces: `_interactive_codex_tui_runner(...) -> str`.
- Produces: `start_interactive_codex_tui(...) -> dict[str, Any]`.
- Consumed by: Task 1 dry-run test and Task 3 status integration.

- [ ] **Step 1: Add TUI constants near existing Codex constants**

Add below `CODEX_STEER_IDLE_SECONDS = 20`:

```python
INTERACTIVE_TUI_APPROVAL_POLICY = "on-request"
INTERACTIVE_TUI_MODE = "interactive_tui"
```

- [ ] **Step 2: Add a JSON writer helper**

Add below `_read_json(...)`:

```python
def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
```

Then update future new code to use `_write_json`. Do not refactor existing callers unless needed for this feature.

- [ ] **Step 3: Add the pure command builder**

Add below `_launch(...)`:

```python
def _codex_tui_args(
    cwd: str,
    sandbox: str,
    approval_policy: str,
    prompt: str,
    resume_session_id: str = "",
    no_alt_screen: bool = False,
) -> list[str]:
    args: list[str] = []
    if resume_session_id.strip():
        args.extend(["resume", resume_session_id.strip()])
    args.extend([
        "-m",
        CODEX_MODEL,
        "-C",
        str(Path(cwd).resolve()),
        "-s",
        sandbox,
        "-a",
        approval_policy or INTERACTIVE_TUI_APPROVAL_POLICY,
        "-c",
        f'model_reasoning_effort="{CODEX_REASONING_EFFORT}"',
        "-c",
        f'service_tier="{CODEX_SERVICE_TIER}"',
    ])
    if no_alt_screen:
        args.append("--no-alt-screen")
    if prompt.strip():
        args.append(prompt.strip())
    return args
```

- [ ] **Step 4: Add the interactive PowerShell runner**

Add below `_codex_runner(...)` or immediately before it if you want launcher helpers grouped first:

```python
def _interactive_codex_tui_runner(
    run_dir: Path,
    cwd: str,
    sandbox: str,
    approval_policy: str,
    prompt: str,
    resume_session_id: str,
    no_alt_screen: bool,
    close_on_exit: bool,
) -> str:
    args = _codex_tui_args(
        cwd=cwd,
        sandbox=sandbox,
        approval_policy=approval_policy,
        prompt=prompt,
        resume_session_id=resume_session_id,
        no_alt_screen=no_alt_screen,
    )
    ps_args = "\n".join([f"$argsList += @({_ps(arg)})" for arg in args])
    keep_open = "$true" if not close_on_exit else "$false"
    return textwrap.dedent(f"""
    $ErrorActionPreference = 'Continue'
    { _PS_CLEANUP_FN }
    $RunDir = {_ps(run_dir)}
    $Cwd = {_ps(cwd)}
    $StatusPath = Join-Path $RunDir 'status.json'
    $DisplayLog = Join-Path $RunDir 'display.log'
    $CodexCmd = {_ps(CODEX)}
    $KeepOpen = {keep_open}

    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::InputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
    $Host.UI.RawUI.WindowTitle = "Codex interactive TUI - $(Split-Path $RunDir -Leaf)"

    function Write-Log([string]$Message) {{
      $line = "[{{0}}] {{1}}" -f (Get-Date).ToString("o"), $Message
      Write-Host $line
      Add-Content -LiteralPath $DisplayLog -Value $line -Encoding UTF8
    }}

    function Set-Status([string]$Status, [int]$ExitCode = 0) {{
      $obj = [ordered]@{{
        status = $Status
        run_id = (Split-Path $RunDir -Leaf)
        updated_at = (Get-Date).ToString("o")
        exit_code = $ExitCode
        mode = "interactive_tui"
      }}
      $obj | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StatusPath -Encoding UTF8
    }}

    Set-Location -LiteralPath $Cwd
    Set-Status "running"
    Write-Log "Starting interactive Codex TUI. This terminal is user-steered; display.log is launcher/status only."

    $argsList = @()
    {ps_args}

    Write-Log ("Command: " + $CodexCmd + " " + ($argsList -join " "))
    & $CodexCmd @argsList
    $exitCode = if ($LASTEXITCODE -eq $null) {{ 0 }} else {{ $LASTEXITCODE }}
    if ($exitCode -eq 0) {{
      Set-Status "closed" $exitCode
      Write-Log "Interactive Codex TUI exited cleanly."
    }} else {{
      Set-Status "failed" $exitCode
      Write-Log ("Interactive Codex TUI exited with code " + $exitCode)
    }}

    if ($KeepOpen) {{
      Write-Host ""
      Read-Host "Codex TUI exited. Press Enter to close this window" | Out-Null
    }}
    """).strip()
```

- [ ] **Step 5: Add the MCP tool**

Add this below `start_visible_first_mate_codex_pool(...)` and before `steer_visible_codex_run(...)`:

```python
@mcp.tool()
def start_interactive_codex_tui(
    prompt: str,
    cwd: str,
    title: str = "Interactive Codex TUI",
    sandbox: str = "read-only",
    approval_policy: str = INTERACTIVE_TUI_APPROVAL_POLICY,
    session_context: str = "",
    resume_session_id: str = "",
    requires_tool_access: bool = False,
    no_alt_screen: bool = False,
    close_on_exit: bool = False,
    model: str = CODEX_MODEL,
    reasoning_effort: str = CODEX_REASONING_EFFORT,
    service_tier: str = CODEX_SERVICE_TIER,
) -> dict[str, Any]:
    """Launch the real interactive Codex TUI in a visible terminal with sidecar metadata."""
    effective_model = CODEX_MODEL
    effective_reasoning = CODEX_REASONING_EFFORT
    effective_service_tier = CODEX_SERVICE_TIER
    auto_full_tool_access = _needs_full_tool_access("\n".join([title, prompt, session_context]))
    effective_sandbox = CODEX_FULL_TOOL_SANDBOX
    requested_approval = approval_policy or INTERACTIVE_TUI_APPROVAL_POLICY
    effective_prompt = _with_session_context_bootstrap(
        "\n\n".join([
            _codex_permission_contract(sandbox, effective_sandbox),
            prompt,
        ]),
        cwd,
        "Interactive Codex TUI",
        session_context,
    )
    run_dir = _make_run(cwd, "codex-tui-resume" if resume_session_id else "codex-tui", title, effective_prompt, {
        "agent": "codex",
        "mode": INTERACTIVE_TUI_MODE,
        "cwd": str(Path(cwd).resolve()),
        "sandbox": effective_sandbox,
        "requested_sandbox": sandbox,
        "approval_policy": requested_approval,
        "model": effective_model,
        "reasoning_effort": effective_reasoning,
        "service_tier": effective_service_tier,
        "requested_model": model,
        "requested_reasoning_effort": reasoning_effort,
        "requested_service_tier": service_tier,
        "resume_session_id": resume_session_id or None,
        "session_context_supplied": bool(session_context.strip()),
        "requires_tool_access": requires_tool_access,
        "auto_full_tool_access": auto_full_tool_access,
        "sandbox_bypass_enabled": True,
        "tool_access_default": "full-process-access",
        "no_alt_screen": bool(no_alt_screen),
        "close_on_exit": bool(close_on_exit),
    })
    (run_dir / "session_context.md").write_text(session_context.strip(), encoding="utf-8")
    (run_dir / "notes.md").write_text(
        "# Interactive Codex TUI Notes\n\n"
        "This run is user-steered through the Codex TUI. display.log contains launcher/status lines, not a full transcript.\n",
        encoding="utf-8",
    )
    (run_dir / "display.log").write_text("", encoding="utf-8")
    script = run_dir / "run.ps1"
    script.write_text(
        _interactive_codex_tui_runner(
            run_dir=run_dir,
            cwd=str(Path(cwd).resolve()),
            sandbox=effective_sandbox,
            approval_policy=requested_approval,
            prompt=effective_prompt,
            resume_session_id=resume_session_id,
            no_alt_screen=no_alt_screen,
            close_on_exit=close_on_exit,
        ),
        encoding="utf-8",
    )
    pid = _launch(script)
    (run_dir / "launcher_pid.txt").write_text(str(pid), encoding="utf-8")
    status = _read_json(run_dir / "status.json", {})
    status.update({
        "status": "launched",
        "mode": INTERACTIVE_TUI_MODE,
        "pid": pid,
        "updated_at": _dt.datetime.now().isoformat(),
    })
    _write_json(run_dir / "status.json", status)
    return {
        "ok": True,
        "run_id": run_dir.name,
        "pid": pid,
        "run_dir": str(run_dir),
        "prompt": str(run_dir / "prompt.md"),
        "session_context": str(run_dir / "session_context.md"),
        "display_log": str(run_dir / "display.log"),
        "status": str(run_dir / "status.json"),
        "session_id": None,
        "session_id_file": str(run_dir / "session_id.txt"),
        "metadata": str(run_dir / "metadata.json"),
        "note": "A real interactive Codex TUI was launched. You can steer it directly in the terminal. The sidecar records metadata and status only; use Codex saved sessions, git diff, and notes for review.",
    }
```

- [ ] **Step 6: Run the dry-run test**

Run:

```powershell
python .\tests\e2e_visible_bridge.py --skip-expensive
```

Expected: the new dry-run case passes. If later real Codex cases fail, fix only regressions introduced by this task.

---

### Task 3: Add Best-Effort Session ID Discovery

**Files:**
- Modify: `visible_agent_bridge.py`
- Modify: `tests/e2e_visible_bridge.py`

**Interfaces:**
- Produces: `_extract_session_id_from_jsonl(path: Path) -> str`.
- Produces: `_find_recent_codex_session_id(started_at: float, cwd: str, limit: int = 50) -> str`.
- Produces: `_record_interactive_session_id(run_dir: Path, metadata: dict[str, Any]) -> str | None`.
- Consumed by: `get_visible_run_status(...)` and `list_visible_runs(...)`.

- [ ] **Step 1: Add helper tests to the dry-run case**

Append to `case_interactive_tui_sidecar_dry_run()` after the status assertions:

```python
    fake_session = run_dir / "fake-session.jsonl"
    fake_session.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "019f-test-session"}}) + "\n",
        encoding="utf-8",
    )
    assert bridge._extract_session_id_from_jsonl(fake_session) == "019f-test-session"
```

- [ ] **Step 2: Add JSONL session-id extraction**

Add below `_write_json(...)`:

```python
def _extract_session_id_from_jsonl(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for _ in range(200):
                line = handle.readline()
                if not line:
                    break
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                payload = event.get("payload") if isinstance(event, dict) else None
                if isinstance(payload, dict) and isinstance(payload.get("id"), str):
                    return payload["id"]
                session_meta = event.get("session_meta") if isinstance(event, dict) else None
                if isinstance(session_meta, dict):
                    nested_payload = session_meta.get("payload")
                    if isinstance(nested_payload, dict) and isinstance(nested_payload.get("id"), str):
                        return nested_payload["id"]
    except Exception:
        return ""
    return ""
```

- [ ] **Step 3: Add session file discovery**

Add below `_extract_session_id_from_jsonl(...)`:

```python
def _find_recent_codex_session_id(started_at: float, cwd: str, limit: int = 50) -> str:
    sessions_root = HOME / ".codex" / "sessions"
    if not sessions_root.exists():
        return ""
    try:
        files = sorted(
            [path for path in sessions_root.rglob("*.jsonl") if path.is_file()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except Exception:
        return ""
    cwd_text = str(Path(cwd).resolve()).lower()
    fallback = ""
    for path in files[: max(1, min(limit, 200))]:
        try:
            if path.stat().st_mtime + 2 < started_at:
                continue
        except Exception:
            continue
        session_id = _extract_session_id_from_jsonl(path)
        if not session_id:
            continue
        if not fallback:
            fallback = session_id
        try:
            sample = path.read_text(encoding="utf-8-sig", errors="replace")[:20000].lower()
        except Exception:
            sample = ""
        if cwd_text and cwd_text in sample:
            return session_id
    return fallback
```

- [ ] **Step 4: Add run-dir recorder**

Add below `_find_recent_codex_session_id(...)`:

```python
def _record_interactive_session_id(run_dir: Path, metadata: dict[str, Any]) -> str | None:
    if metadata.get("mode") != INTERACTIVE_TUI_MODE:
        return None
    session_path = run_dir / "session_id.txt"
    if session_path.exists():
        value = session_path.read_text(encoding="utf-8-sig").strip()
        return value or None
    started_at = float(metadata.get("started_at_epoch") or metadata.get("created_at_epoch") or 0.0)
    cwd = str(metadata.get("cwd") or _infer_cwd_from_run_dir(run_dir, metadata))
    if started_at <= 0:
        try:
            started_at = (run_dir / "metadata.json").stat().st_mtime
        except Exception:
            started_at = time.time()
    session_id = _find_recent_codex_session_id(started_at, cwd)
    if not session_id:
        return None
    session_path.write_text(session_id, encoding="utf-8")
    metadata["session_id"] = session_id
    metadata["session_id_detected_at"] = _dt.datetime.now().isoformat()
    _write_json(run_dir / "metadata.json", metadata)
    return session_id
```

- [ ] **Step 5: Store epoch metadata when launching**

In the `start_interactive_codex_tui(...)` metadata dict, add:

```python
        "started_at_epoch": time.time(),
```

- [ ] **Step 6: Call the recorder from status/list functions**

In `get_visible_run_status(...)`, after reading `metadata`, add:

```python
    detected_session_id = _record_interactive_session_id(path, metadata)
```

Change the returned `session_id` line to:

```python
        "session_id": session_path.read_text(encoding="utf-8-sig").strip() if session_path.exists() else detected_session_id,
```

In `list_visible_runs(...)`, after reading metadata for each run, assign it to a variable:

```python
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig")) if metadata_path.exists() else {}
        detected_session_id = _record_interactive_session_id(run, metadata)
```

Then use `metadata` in the result and change `session_id` to:

```python
            "session_id": session_path.read_text(encoding="utf-8-sig").strip() if session_path.exists() else detected_session_id,
```

- [ ] **Step 7: Run the dry-run test**

Run:

```powershell
python .\tests\e2e_visible_bridge.py --skip-expensive
```

Expected: PASS through the new TUI dry-run case and existing non-expensive cases.

---

### Task 4: Document and Expose the Interactive TUI Tool

**Files:**
- Modify: `README.md`
- Modify: `plugin/skills/claude-manages-codex/SKILL.md`
- Modify during rollout: `C:\Users\jonny\.claude\settings.json`

**Interfaces:**
- Consumes: `start_interactive_codex_tui(...)`.
- Produces: user-facing docs and Claude skill instructions that route direct human steering to TUI mode.

- [ ] **Step 1: Update README tool list**

In `README.md`, add this bullet after `start_visible_first_mate_codex_pool`:

```markdown
- `start_interactive_codex_tui` - launch the real interactive Codex TUI in a visible terminal so the user can steer Codex directly, while the bridge records sidecar metadata.
```

- [ ] **Step 2: Update README current behavior**

Add this bullet in `## Current bridge behavior`:

```markdown
- Interactive TUI runs use top-level `codex` rather than `codex exec --json`; they are user-steered, default to `on-request` approvals, and record sidecar metadata instead of structured JSONL event logs.
```

- [ ] **Step 3: Add README usage guidance**

Add this section before `## E2E verification`:

```markdown
## Interactive TUI Mode

Use `start_interactive_codex_tui` when you want to type directly into Codex instead of steering through Claude or a queued bridge message.

This mode opens the real Codex TUI in a visible terminal. The user can approve, reject, and steer inside that terminal. The bridge still creates `.claude-codex/runs/<run-id>/` with `prompt.md`, `session_context.md`, `metadata.json`, `status.json`, `notes.md`, and best-effort `session_id.txt`.

This mode is intentionally lower-fidelity than `codex exec --json`: `display.log` contains launcher/status lines, not a full transcript. For automated worker steering and structured event logs, keep using `start_visible_codex_worker`.
```

- [ ] **Step 4: Update README allowlist example**

Add this permission entry:

```json
"mcp__plugin_claude-manages-codex_agent-visibility__start_interactive_codex_tui",
```

- [ ] **Step 5: Update Claude skill tool list**

In `plugin/skills/claude-manages-codex/SKILL.md`, add this bullet in `## Visible Agent Harness`:

```markdown
- `start_interactive_codex_tui`: launches the real interactive Codex TUI in a visible terminal for direct user steering, with bridge sidecar metadata but no structured JSONL event stream.
```

- [ ] **Step 6: Update Claude skill routing guidance**

Add this paragraph after the visible harness use cases:

```markdown
Use `start_interactive_codex_tui` when the user explicitly wants to type into Codex directly, approve actions in the Codex TUI, or steer the worker without routing every message through Claude. Treat this mode as user-steered: Claude provides the initial architecture brief and later review, but should not expect `steer_visible_codex_run` to inject live text into the TUI.
```

- [ ] **Step 7: Update local Claude allowlist during rollout**

Use a structured JSON edit, not string concatenation, to add:

```json
"mcp__plugin_claude-manages-codex_agent-visibility__start_interactive_codex_tui"
```

to `C:\Users\jonny\.claude\settings.json` under `permissions.allow`.

- [ ] **Step 8: Validate docs and JSON**

Run:

```powershell
python -m json.tool C:\Users\jonny\.claude\settings.json > $null
git diff --check
```

Expected: both commands exit 0.

---

### Task 5: Sync Live Files and Run Verification

**Files:**
- Modify live: `C:\Users\jonny\.agent-bridge\visible_agent_bridge.py`
- Modify live: `C:\Users\jonny\.claude\skills\claude-manages-codex\skills\claude-manages-codex\SKILL.md`

**Interfaces:**
- Consumes: source bridge and skill files.
- Produces: live MCP-visible bridge update after Claude reload/restart.

- [ ] **Step 1: Compile Python files**

Run:

```powershell
python -m py_compile visible_agent_bridge.py tests\e2e_visible_bridge.py
```

Expected: exit 0.

- [ ] **Step 2: Run non-expensive E2E**

Run:

```powershell
python .\tests\e2e_visible_bridge.py --skip-expensive
```

Expected: the dry-run interactive TUI case passes and existing visible worker/resume/interrupt cases pass.

- [ ] **Step 3: Run full E2E after committing source changes**

Because the E2E has a clean-worktree guard, commit source changes before this step. Then run:

```powershell
python .\tests\e2e_visible_bridge.py
```

Expected: all 8 cases pass.

- [ ] **Step 4: Run a manual real TUI smoke**

Launch one real interactive TUI using the new tool from a live Claude session or a direct Python harness. Use a harmless prompt:

```text
Reply with INTERACTIVE_TUI_SMOKE_OK, do not edit files, then wait for my next message.
```

In the opened Codex TUI, type:

```text
Thanks. Please exit after confirming INTERACTIVE_TUI_MANUAL_STEER_OK.
```

Expected:

- a real Codex TUI opens, not `codex exec --json`
- the user can type directly
- Codex responds in the TUI
- `get_visible_run_status` reports `metadata.mode == "interactive_tui"`
- `display.log` contains launcher/status lines
- `session_id.txt` is present or the status response clearly reports `session_id: null`

- [ ] **Step 5: Sync source to live bridge paths**

Run:

```powershell
Copy-Item .\visible_agent_bridge.py C:\Users\jonny\.agent-bridge\visible_agent_bridge.py -Force
Copy-Item .\plugin\skills\claude-manages-codex\SKILL.md C:\Users\jonny\.claude\skills\claude-manages-codex\skills\claude-manages-codex\SKILL.md -Force
```

- [ ] **Step 6: Verify live sync text**

Run:

```powershell
rg "start_interactive_codex_tui|interactive Codex TUI|interactive_tui" C:\Users\jonny\.agent-bridge\visible_agent_bridge.py C:\Users\jonny\.claude\skills\claude-manages-codex\skills\claude-manages-codex\SKILL.md C:\Users\jonny\.claude\settings.json
```

Expected: all three live files contain the new tool or allowlist text.

- [ ] **Step 7: Commit and push**

Use the personal GitHub identity:

```powershell
git status --short
git add visible_agent_bridge.py tests\e2e_visible_bridge.py README.md plugin\skills\claude-manages-codex\SKILL.md
git -c user.name="JonathanLiu1401" -c user.email="jonathan.liu1401@gmail.com" commit -m "feat(bridge): add interactive codex tui sidecar"
git push origin main
```

- [ ] **Step 8: Final status checks**

Run:

```powershell
git status --short --branch
git log -1 --oneline --decorate
```

Expected:

```text
## main...origin/main
<commit> (HEAD -> main, origin/main) feat(bridge): add interactive codex tui sidecar
```

---

## Self-Review

- Spec coverage: The plan covers the new TUI tool, top-level `codex` launch, sidecar files, best-effort session id capture, Claude management semantics, error handling, tests, docs, sync, and reload caveat.
- Scope: One new launcher mode plus docs and tests. Existing JSON exec worker behavior remains unchanged.
- Testability: Automated dry-run tests cover command construction and sidecar files without opening a TUI. Manual smoke covers the direct human steering behavior that automation cannot reliably prove.
- Type consistency: New helper names are `_codex_tui_args`, `_interactive_codex_tui_runner`, `_extract_session_id_from_jsonl`, `_find_recent_codex_session_id`, `_record_interactive_session_id`, and `start_interactive_codex_tui`.
