from __future__ import annotations

import argparse
import datetime as dt
import inspect
import json
import os
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import visible_agent_bridge as bridge


SESSION_CONTEXT = (
    "Self-contained E2E verification for the Claude-Codex visible bridge. "
    "Do not use read-past-sessions. Do not edit files. Return the requested marker exactly."
)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    return default


def _run_dir(result: dict[str, Any]) -> Path:
    return Path(result["run_dir"]).resolve()


def _tail(path: Path, lines: int = 120) -> str:
    if not path.exists():
        return "<missing display.log>"
    data = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    return "\n".join(data[-lines:])


def _status(run_dir: Path) -> str:
    value = _read_json(run_dir / "status.json", {"status": "missing"})
    return str(value.get("status", "missing"))


def _thread_id(run_dir: Path) -> str:
    path = run_dir / "thread_id.txt"
    return path.read_text(encoding="utf-8-sig").strip() if path.exists() else ""


def _pid_exists(pid: str) -> bool:
    if not pid.strip():
        return False
    check = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            f"if (Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue) {{ exit 0 }} else {{ exit 1 }}",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return check.returncode == 0


def _assert_launcher_exited(run_dir: Path) -> None:
    pid_path = run_dir / "launcher_pid.txt"
    if not pid_path.exists():
        return
    pid = pid_path.read_text(encoding="utf-8-sig").strip()
    deadline = time.time() + 20
    while time.time() < deadline:
        if not _pid_exists(pid):
            return
        time.sleep(1)
    raise AssertionError(f"launcher process still alive after run completion: pid={pid} run={run_dir}")


def _assert_model_policy() -> None:
    saved_model = os.environ.get(bridge.CLAUDE_ADVISOR_MODEL_ENV)
    saved_until = os.environ.get(bridge.CLAUDE_ADVISOR_MODEL_UNTIL_ENV)
    try:
        os.environ.pop(bridge.CLAUDE_ADVISOR_MODEL_ENV, None)
        os.environ.pop(bridge.CLAUDE_ADVISOR_MODEL_UNTIL_ENV, None)
        assert bridge._default_claude_advisor_model(dt.date(2026, 7, 7)) == "fable"
        assert bridge._default_claude_advisor_model(dt.date(2026, 7, 8)) == "opus"
        os.environ[bridge.CLAUDE_ADVISOR_MODEL_ENV] = "opus"
        assert bridge._default_claude_advisor_model(dt.date(2026, 7, 1)) == "opus"
    finally:
        if saved_model is None:
            os.environ.pop(bridge.CLAUDE_ADVISOR_MODEL_ENV, None)
        else:
            os.environ[bridge.CLAUDE_ADVISOR_MODEL_ENV] = saved_model
        if saved_until is None:
            os.environ.pop(bridge.CLAUDE_ADVISOR_MODEL_UNTIL_ENV, None)
        else:
            os.environ[bridge.CLAUDE_ADVISOR_MODEL_UNTIL_ENV] = saved_until


def _assert_codex_mcp_tool_allowlists() -> None:
    required = {"request_captain_help", "submit_captain_report"}

    manifest = _read_json(ROOT / "codex-plugin" / ".mcp.json", {})
    manifest_tools = set(
        manifest.get("mcpServers", {})
        .get("agent-visibility", {})
        .get("enabled_tools", [])
    )
    assert required <= manifest_tools, {"source_manifest": sorted(manifest_tools), "missing": sorted(required - manifest_tools)}

    config_path = Path.home() / ".codex" / "config.toml"
    if config_path.exists():
        config = tomllib.loads(config_path.read_text(encoding="utf-8-sig"))
        active_tools = set(
            config.get("plugins", {})
            .get("codex-consults-claude@personal", {})
            .get("mcp_servers", {})
            .get("agent-visibility", {})
            .get("enabled_tools", [])
        )
        assert required <= active_tools, {"active_config": sorted(active_tools), "missing": sorted(required - active_tools)}


def case_captain_help_mailbox() -> dict[str, Any]:
    run_dir = bridge._make_run(
        str(ROOT),
        "codex",
        "E2E captain help mailbox",
        "Self-contained mailbox test. Do not launch Codex.",
        {
            "agent": "codex",
            "cwd": str(ROOT),
            "requested_sandbox": "read-only",
            "approval_policy": "never",
        },
    )
    request = bridge.request_captain_help(
        str(run_dir),
        question="Need captain decision between option A and option B.",
        context="Observed facts are self-contained for this mailbox test.",
        urgency="blocked",
        recommended_next="Pick option A for this E2E.",
    )
    assert request["ok"], request
    status = bridge.get_visible_run_status(str(run_dir), tail_lines=5)
    assert status["pending_help_requests"] == 1, status

    response = bridge.respond_to_captain_help_request(
        str(run_dir),
        request["request_id"],
        response="Captain decision: use option A. Continue and report E2E_CAPTAIN_HELP_OK.",
        session_context=SESSION_CONTEXT,
        sandbox="read-only",
        launch_if_closed=False,
    )
    assert response["ok"], response
    assert response["steer"]["mode"] in {"queued", "queued_no_active_runner"}, response
    status = bridge.get_visible_run_status(str(run_dir), tail_lines=5)
    assert status["pending_help_requests"] == 0, status
    assert status["answered_help_requests"] == 1, status
    assert status["pending_steers"] == 1, status
    return {"run_dir": str(run_dir), "request_id": request["request_id"]}


# Deprecated-path regression: the single-worker TUI launcher must remain functional.
def case_interactive_tui_sidecar_dry_run() -> dict[str, Any]:
    original_launch = bridge._launch_interactive_terminal
    launched_scripts: list[Path] = []

    def fake_launch(script_path: Path) -> int:
        launched_scripts.append(script_path)
        return 424242

    try:
        bridge._launch_interactive_terminal = fake_launch  # type: ignore[assignment]
        result = bridge.start_interactive_codex_tui(
            prompt="Self-contained interactive TUI dry-run. Do not edit files.",
            cwd=str(ROOT),
            title="E2E interactive Codex TUI dry-run",
            sandbox="read-only",
            approval_policy="on-request",
            session_context=SESSION_CONTEXT,
            no_alt_screen=True,
        )
    finally:
        bridge._launch_interactive_terminal = original_launch  # type: ignore[assignment]

    assert result["ok"], result
    assert result["pid"] == 424242, result
    assert launched_scripts, result
    assert "watch_command" in result and "captain_reports/final.json" in result["watch_command"], result

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
    assert metadata["close_on_exit"] is True, metadata
    assert metadata["auto_close_after_report"] is True, metadata
    assert status["status"] == "launched", status

    prompt = (run_dir / "prompt.md").read_text(encoding="utf-8-sig")
    assert "submit_captain_report" in prompt, prompt
    assert str(run_dir) in prompt, prompt
    assert "Do not rely on a normal TUI final answer to reach Claude" in prompt, prompt
    assert "Captain Report Handoff" in prompt, prompt

    assert "codex.cmd" in script, script
    assert "'-m'" in script and "'gpt-5.6-sol'" in script, script
    assert "'-a'" in script and "'on-request'" in script, script
    assert "model_reasoning_effort=`\"xhigh`\"" in script, script
    assert "service_tier=`\"fast`\"" in script, script
    assert "--no-alt-screen" in script, script
    assert "$KeepOpen = $false" in script, script
    assert "$AutoCloseAfterReport = $true" in script, script
    assert "GenerateConsoleCtrlEvent" in script, script
    assert "taskkill.exe" in script, script
    assert "Close-InteractiveTuiTree" in script, script
    assert "captain_reports" in script and "final.json" in script, script
    assert "--json" not in script, script
    assert "exec" not in script.split("$argsList", 1)[1].split("Write-Log", 1)[0], script

    assert (run_dir / "prompt.md").exists(), run_dir
    assert (run_dir / "session_context.md").exists(), run_dir
    assert (run_dir / "notes.md").exists(), run_dir
    assert (run_dir / "display.log").exists(), run_dir
    assert (run_dir / "captain_reports").is_dir(), run_dir

    # Long captain briefs must not be passed inline: codex.cmd is a cmd.exe
    # batch shim capped at 8191 chars of command line, so oversized briefs go
    # through prompt.md with a short bootstrap argument.
    long_scripts: list[Path] = []

    def fake_launch_long(script_path: Path) -> int:
        long_scripts.append(script_path)
        return 424243

    try:
        bridge._launch_interactive_terminal = fake_launch_long  # type: ignore[assignment]
        long_result = bridge.start_interactive_codex_tui(
            prompt="Self-contained interactive TUI long-brief dry-run. Do not edit files.",
            cwd=str(ROOT),
            title="E2E interactive TUI long-brief dry-run",
            sandbox="read-only",
            approval_policy="on-request",
            session_context="LONG-BRIEF-PADDING " * 600,
            no_alt_screen=True,
        )
    finally:
        bridge._launch_interactive_terminal = original_launch  # type: ignore[assignment]
    long_run_dir = _run_dir(long_result)
    long_script = long_scripts[0].read_text(encoding="utf-8-sig")
    assert "too long for the Windows command line" in long_script, long_script
    assert "LONG-BRIEF-PADDING" not in long_script, "long brief leaked into the TUI command line"
    long_prompt = (long_run_dir / "prompt.md").read_text(encoding="utf-8-sig")
    assert "LONG-BRIEF-PADDING" in long_prompt, long_prompt

    original_find_session = bridge._find_recent_codex_session_id
    try:
        bridge._find_recent_codex_session_id = lambda started_at, cwd, limit=50: ""  # type: ignore[assignment]
        report = bridge.submit_captain_report(
            str(run_dir),
            outcome="completed",
            summary="Interactive TUI dry-run report reached the captain sidecar.",
            changed_files=[],
            verification=["dry-run launcher inspected"],
            risks=["none"],
            questions=[],
            close_tui=False,
        )
        reported_status = bridge.get_visible_run_status(str(run_dir), tail_lines=20)
    finally:
        bridge._find_recent_codex_session_id = original_find_session  # type: ignore[assignment]
    assert report["ok"], report
    assert Path(report["report"]).exists(), report
    assert Path(report["report_markdown"]).exists(), report
    assert reported_status["captain_report"]["outcome"] == "completed", reported_status
    assert reported_status["captain_reports_count"] >= 1, reported_status

    fallback_report = {
        "run_dir": str(run_dir),
        "outcome": "completed",
        "summary": "Fallback final.json report is captain-readable.",
        "changed_files": [],
        "verification": ["fallback report inspected"],
        "risks": [],
        "questions": [],
        "close_tui": True,
    }
    (run_dir / "captain_reports" / "final.json").write_text(json.dumps(fallback_report, indent=2), encoding="utf-8")
    (run_dir / "status.json").write_text(json.dumps({"status": "running", "mode": "interactive_tui"}, indent=2), encoding="utf-8")
    try:
        bridge._find_recent_codex_session_id = lambda started_at, cwd, limit=50: ""  # type: ignore[assignment]
        fallback_status = bridge.get_visible_run_status(str(run_dir), tail_lines=20)
    finally:
        bridge._find_recent_codex_session_id = original_find_session  # type: ignore[assignment]
    assert fallback_status["status"]["status"] == "reported", fallback_status
    assert fallback_status["status"]["outcome"] == "completed", fallback_status
    assert fallback_status["captain_reports_count"] >= 1, fallback_status

    find_calls: list[tuple[float, str, int]] = []

    def fake_find_session(started_at: float, cwd: str, limit: int = 50) -> str:
        find_calls.append((started_at, cwd, limit))
        return ""

    try:
        bridge._find_recent_codex_session_id = fake_find_session  # type: ignore[assignment]
        status_result = bridge.get_visible_run_status(str(run_dir), tail_lines=20)
        assert status_result["metadata"]["mode"] == "interactive_tui", status_result
        assert status_result["session_id"] is None, status_result
        assert not (run_dir / "session_id.txt").exists(), run_dir

        listed = bridge.list_visible_runs(str(ROOT), limit=5)
        listed_run = next((item for item in listed if item["run_dir"] == str(run_dir)), None)
        assert listed_run is not None and listed_run["metadata"].get("mode") == "interactive_tui", listed
        assert listed_run["session_id"] is None, listed_run
        assert not (run_dir / "session_id.txt").exists(), run_dir
    finally:
        bridge._find_recent_codex_session_id = original_find_session  # type: ignore[assignment]
    assert find_calls, status_result

    fake_session = run_dir / "fake-session.jsonl"
    fake_session.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "019f-test-session"}}) + "\n",
        encoding="utf-8",
    )
    assert bridge._extract_session_id_from_jsonl(fake_session) == "019f-test-session"

    metadata_path = run_dir / "metadata.json"
    original_metadata = metadata_path.read_text(encoding="utf-8-sig")
    original_write_json = bridge._write_json
    original_path_write_text = Path.write_text

    def assert_best_effort_failure(
        label: str,
        metadata_override: dict[str, Any] | None = None,
        find_session: Any = None,
        write_text: Any = None,
        write_json: Any = None,
    ) -> None:
        if (run_dir / "session_id.txt").exists():
            (run_dir / "session_id.txt").unlink()
        metadata_path.write_text(original_metadata, encoding="utf-8")
        if metadata_override:
            failing_metadata = _read_json(metadata_path, {})
            failing_metadata.update(metadata_override)
            metadata_path.write_text(json.dumps(failing_metadata, indent=2), encoding="utf-8")
        bridge._find_recent_codex_session_id = find_session or (lambda started_at, cwd, limit=50: "")
        bridge._write_json = write_json or original_write_json  # type: ignore[assignment]
        Path.write_text = write_text or original_path_write_text  # type: ignore[assignment]
        try:
            failure_status = bridge.get_visible_run_status(str(run_dir), tail_lines=20)
            assert failure_status["session_id"] is None, (label, failure_status)
            assert not (run_dir / "session_id.txt").exists(), label
            failure_list = bridge.list_visible_runs(str(ROOT), limit=5)
            failure_item = next(item for item in failure_list if item["run_dir"] == str(run_dir))
            assert failure_item["session_id"] is None, (label, failure_item)
            assert not (run_dir / "session_id.txt").exists(), label
        finally:
            bridge._find_recent_codex_session_id = original_find_session  # type: ignore[assignment]
            bridge._write_json = original_write_json  # type: ignore[assignment]
            Path.write_text = original_path_write_text  # type: ignore[assignment]
            if (run_dir / "session_id.txt").exists():
                (run_dir / "session_id.txt").unlink()
            metadata_path.write_text(original_metadata, encoding="utf-8")

    assert_best_effort_failure("invalid started_at", metadata_override={"started_at_epoch": "not-a-float"})

    def raise_discovery(started_at: float, cwd: str, limit: int = 50) -> str:
        raise RuntimeError("discovery failed")

    assert_best_effort_failure("discovery failure", find_session=raise_discovery)

    def raise_session_write(self: Path, *args: Any, **kwargs: Any) -> int:
        if self == run_dir / "session_id.txt":
            raise OSError("session write failed")
        return original_path_write_text(self, *args, **kwargs)

    assert_best_effort_failure(
        "session_id write failure",
        find_session=lambda started_at, cwd, limit=50: "019f-write-failure",
        write_text=raise_session_write,
    )

    def raise_write_json(path: Path, value: Any) -> None:
        raise OSError("metadata write failed")

    assert_best_effort_failure(
        "metadata write failure",
        find_session=lambda started_at, cwd, limit=50: "019f-metadata-failure",
        write_json=raise_write_json,
    )

    return {"run_dir": str(run_dir), "script": str(launched_scripts[0])}


# Deprecated-path regression: the first-mate TUI launcher must remain functional.
def case_interactive_first_mate_tui_dry_run() -> dict[str, Any]:
    original_launch = bridge._launch_interactive_terminal
    launched_scripts: list[Path] = []

    def fake_launch(script_path: Path) -> int:
        launched_scripts.append(script_path)
        return 424243

    try:
        bridge._launch_interactive_terminal = fake_launch  # type: ignore[assignment]
        result = bridge.start_interactive_first_mate_codex_tui(
            goal="Self-contained interactive first-mate TUI dry-run. Do not edit files.",
            cwd=str(ROOT),
            scout_areas=["Confirm this dry-run keeps the first-mate prompt contract."],
            implementation_items=[],
            sandbox="read-only",
            approval_policy="on-request",
            max_workers=2,
            session_context=SESSION_CONTEXT,
            no_alt_screen=True,
        )
    finally:
        bridge._launch_interactive_terminal = original_launch  # type: ignore[assignment]

    assert result["ok"], result
    assert result["pid"] == 424243, result
    assert launched_scripts, result

    run_dir = _run_dir(result)
    script = launched_scripts[0].read_text(encoding="utf-8-sig")
    prompt = (run_dir / "prompt.md").read_text(encoding="utf-8-sig")
    metadata = _read_json(run_dir / "metadata.json", {})

    assert metadata["mode"] == "interactive_tui", metadata
    assert metadata["approval_policy"] == "on-request", metadata
    assert metadata["requested_sandbox"] == "read-only", metadata
    assert metadata["model"] == bridge.CODEX_MODEL, metadata
    assert metadata["auto_close_after_report"] is True, metadata
    assert "Use the `firstmate` skill" in prompt, prompt
    assert "submit_captain_report" in prompt, prompt
    assert "Captain Report Handoff" in prompt, prompt
    assert "Keep fan-out bounded to at most 2 workers." in prompt, prompt
    assert "Claude-requested permission intent: read-only" in prompt, prompt
    assert "Self-contained interactive first-mate TUI dry-run" in prompt, prompt
    assert "Confirm this dry-run keeps the first-mate prompt contract." in prompt, prompt
    assert "codex.cmd" in script, script
    assert "--no-alt-screen" in script, script
    assert "--json" not in script, script
    assert "exec" not in script.split("$argsList", 1)[1].split("Write-Log", 1)[0], script
    return {"run_dir": str(run_dir), "script": str(launched_scripts[0])}


def _wait_completed(run_dir: Path, markers: list[str], timeout_s: int = 300) -> str:
    display = run_dir / "display.log"
    deadline = time.time() + timeout_s
    last_status = "missing"
    last_text = ""
    while time.time() < deadline:
        last_status = _status(run_dir)
        if display.exists():
            last_text = display.read_text(encoding="utf-8-sig", errors="replace")
        marker_ok = all(marker in last_text for marker in markers)
        if last_status.startswith("failed"):
            raise AssertionError(f"run failed: {run_dir}\nstatus={last_status}\n{_tail(display)}")
        if last_status in {"completed", "completed_budget_capped"} and marker_ok:
            _assert_launcher_exited(run_dir)
            return last_text
        time.sleep(2)
    missing = [marker for marker in markers if marker not in last_text]
    raise AssertionError(
        f"timed out waiting for {run_dir}\nstatus={last_status}\nmissing={missing}\n{_tail(display)}"
    )


def _assert_no_git_changes() -> None:
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    ).stdout.rstrip("\n")
    allowed_paths = {
        "README.md",
        "plugin/skills/claude-manages-codex/SKILL.md",
        "visible_agent_bridge.py",
        "tests/",
    }
    allowed_prefixes = (
        " M README.md",
        "M  README.md",
        "M README.md",
        " M plugin/skills/claude-manages-codex/SKILL.md",
        "M  plugin/skills/claude-manages-codex/SKILL.md",
        "M plugin/skills/claude-manages-codex/SKILL.md",
        " M visible_agent_bridge.py",
        "M  visible_agent_bridge.py",
        "M visible_agent_bridge.py",
        " M tests/",
        "M  tests/",
        "M tests/",
        "?? tests/",
    )
    unexpected = [
        line
        for line in status.splitlines()
        if line
        and not any(line.startswith(prefix) for prefix in allowed_prefixes)
        and line[3:] not in allowed_paths
    ]
    if unexpected:
        raise AssertionError(f"unexpected git changes from E2E:\n{status}")


def case_visible_worker_and_queued_steer() -> dict[str, Any]:
    result = bridge.start_visible_codex_worker(
        prompt="Self-contained E2E. Do not edit files. Reply exactly E2E_INITIAL_OK.",
        cwd=str(ROOT),
        title="E2E visible worker queued steering",
        sandbox="read-only",
        session_context=SESSION_CONTEXT,
        steer_idle_seconds=10,
    )
    run_dir = _run_dir(result)
    steer = bridge.steer_visible_codex_run(
        str(run_dir),
        "Self-contained steering E2E. Reply exactly E2E_STEERED_OK. Do not edit files.",
        title="E2E queued steering",
        sandbox="read-only",
        session_context=SESSION_CONTEXT,
        launch_if_closed=False,
        interrupt_current_turn=False,
    )
    assert steer["ok"] and steer["mode"] == "queued", steer
    assert "watch_command" in result and "CODEX-RUN-TERMINAL" in result["watch_command"], result
    _wait_completed(run_dir, ["E2E_INITIAL_OK", "E2E_STEERED_OK"], timeout_s=360)
    git_bash = r"C:\Program Files\Git\bin\bash.exe"
    watch = subprocess.run(
        [git_bash if os.path.exists(git_bash) else "bash", "-c", result["watch_command"]],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert watch.returncode == 0 and "CODEX-RUN-TERMINAL" in watch.stdout, watch.stdout
    status = bridge.get_visible_run_status(str(run_dir), tail_lines=30)
    assert status["thread_id"], status
    assert status["pending_steers"] == 0, status
    assert status["completed_steers"] >= 1, status
    return {"run_dir": str(run_dir), "thread_id": status["thread_id"]}


def case_closed_run_resume(previous: dict[str, Any]) -> dict[str, Any]:
    old_run = Path(previous["run_dir"])
    steer = bridge.steer_visible_codex_run(
        str(old_run),
        "Self-contained closed-run resume E2E. Reply exactly E2E_RESUMED_OK. Do not edit files.",
        title="E2E closed run resume",
        sandbox="workspace-write",
        session_context=SESSION_CONTEXT,
        launch_if_closed=True,
    )
    assert steer["ok"] and steer["mode"] == "launched_resume", steer
    run_dir = _run_dir(steer["followup_run"])
    _wait_completed(run_dir, ["E2E_RESUMED_OK"], timeout_s=300)
    assert _thread_id(run_dir) == previous["thread_id"], (run_dir, previous)
    metadata = _read_json(run_dir / "metadata.json", {})
    assert metadata.get("requested_sandbox") == "workspace-write", metadata
    old_status = bridge.get_visible_run_status(str(old_run), tail_lines=10)
    assert old_status["pending_steers"] == 0, old_status
    return {"run_dir": str(run_dir), "thread_id": previous["thread_id"]}


def case_interrupt_steering() -> dict[str, Any]:
    result = bridge.start_visible_codex_worker(
        prompt=(
            "Self-contained interrupt E2E. Do not edit files. First run "
            "`powershell -NoProfile -Command Start-Sleep -Seconds 120`, then reply SHOULD_NOT_REACH."
        ),
        cwd=str(ROOT),
        title="E2E interrupt steering",
        sandbox="read-only",
        session_context=SESSION_CONTEXT,
        steer_idle_seconds=5,
    )
    run_dir = _run_dir(result)
    deadline = time.time() + 120
    while time.time() < deadline and not _thread_id(run_dir):
        time.sleep(1)
    assert _thread_id(run_dir), _tail(run_dir / "display.log")
    steer = bridge.steer_visible_codex_run(
        str(run_dir),
        "Interrupt steering E2E. Stop the old sleep turn and reply exactly E2E_INTERRUPTED_OK. Do not edit files.",
        title="E2E interrupt follow-up",
        sandbox="read-only",
        session_context=SESSION_CONTEXT,
        interrupt_current_turn=True,
        launch_if_closed=True,
    )
    assert steer["ok"], steer
    launched_modes = {"launched_resume", "launched_restart_after_interrupt"}
    assert steer["mode"] in launched_modes | {"queued_interrupt_failed", "queued_no_interrupt_no_pid"}, steer
    if steer["mode"] not in launched_modes:
        raise AssertionError(f"interrupt did not launch follow-up run: {steer}")
    followup = _run_dir(steer["followup_run"])
    _wait_completed(followup, ["E2E_INTERRUPTED_OK"], timeout_s=300)
    return {"run_dir": str(followup), "mode": steer["mode"], "thread_id": _thread_id(followup)}


def case_supervision_review_cycle() -> dict[str, Any]:
    skill_text = (
        ROOT / "plugin" / "skills" / "claude-manages-codex" / "SKILL.md"
    ).read_text(encoding="utf-8")
    required_contract = (
        "## Mandatory 10-Minute Direct Supervision",
        "not a liveness probe",
        "on-track / off-track verdict",
        "A steer issued without first reading the recent work is not supervision",
        "A liveness or status-only poll never counts.",
        "always spawns as a non-interactive visible CLI worker by default",
        "The interactive TUI tools are deprecated because they can flash-close",
        "cannot receive programmatic steering in an open TUI",
        "Use a TUI only when the user explicitly asks for a hands-on interactive Codex terminal",
        "when in doubt, spawn the non-interactive worker",
        "## Parallel Fan-Out Contract",
        "Serial spawning is a manager error, not a bridge limit.",
        "spawn every non-interactive worker first, before reading any result",
        "## Completion Watcher Contract",
        "Never end a turn waiting for Codex without a watcher armed",
        "## Codex Run Ownership and Subagent Handoff",
        "exactly one owner: the main Claude manager loop",
        "Codex runs handed off",
    )
    for phrase in required_contract:
        assert phrase in skill_text, phrase

    result = bridge.start_visible_codex_worker(
        prompt=(
            'Self-contained supervision E2E. Do not edit files. Reply with exactly '
            '"SUPERVISION_PHASE_1 current-assumption: awaiting captain review" and '
            "nothing else, then stop."
        ),
        cwd=str(ROOT),
        title="E2E supervision review cycle",
        sandbox="read-only",
        session_context=SESSION_CONTEXT,
        steer_idle_seconds=90,
    )
    run_dir = _run_dir(result)
    display = run_dir / "display.log"
    deadline = time.time() + 240
    reviewed_line = ""
    while time.time() < deadline:
        if display.exists():
            lines = display.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            reviewed_line = next((line for line in lines if "SUPERVISION_PHASE_1" in line), "")
        if reviewed_line:
            break
        time.sleep(2)
    if not reviewed_line:
        raise AssertionError(f"timed out waiting for SUPERVISION_PHASE_1: {run_dir}\n{_tail(display)}")

    steer = bridge.steer_visible_codex_run(
        run_dir=str(run_dir),
        instruction=(
            f'Captain supervision pass. I reviewed your latest output: "{reviewed_line}". '
            "Verdict: on-track. Now reply with exactly SUPERVISION_PASS_OK and nothing else."
        ),
        interrupt_current_turn=False,
    )
    assert steer["ok"], steer
    steer_sig = inspect.signature(bridge.steer_visible_codex_run)
    assert (
        steer_sig.parameters["interrupt_current_turn"].default is True
    ), "steer_visible_codex_run must deliver directly (interrupt) by default"
    _wait_completed(run_dir, ["SUPERVISION_PHASE_1", "SUPERVISION_PASS_OK"], timeout_s=360)

    steer_files = sorted((run_dir / "steer_done").glob("*.md"))
    if not steer_files:
        steer_files = sorted((run_dir / "steer_queue").glob("*.md"))
    assert steer_files, steer
    steer_text = steer_files[-1].read_text(encoding="utf-8")
    assert "SUPERVISION_PHASE_1" in steer_text, steer_text
    return {"run_dir": str(run_dir), "reviewed_line": reviewed_line}


def case_haiku_composed_worker() -> dict[str, Any]:
    result = bridge.start_visible_haiku_composed_codex_worker(
        prompt_brief=(
            "Self-contained E2E. Ask Codex to do no file edits and reply exactly E2E_HAIKU_OK."
        ),
        cwd=str(ROOT),
        title="E2E Haiku composed Codex worker",
        sandbox="read-only",
        session_context=SESSION_CONTEXT,
        composer_max_budget_usd=bridge.CLAUDE_PROMPT_COMPOSER_MAX_BUDGET_USD,
        steer_idle_seconds=5,
    )
    run_dir = _run_dir(result)
    _wait_completed(run_dir, ["E2E_HAIKU_OK"], timeout_s=360)
    assert (run_dir / "composer_events.jsonl").exists(), run_dir
    assert (run_dir / "composed_prompt.md").exists(), run_dir
    return {"run_dir": str(run_dir), "thread_id": _thread_id(run_dir)}


def case_first_mate_pool() -> dict[str, Any]:
    result = bridge.start_visible_first_mate_codex_pool(
        goal=(
            "Self-contained E2E only. Do not edit files and do not spawn subagents. "
            "Reply exactly E2E_FIRSTMATE_OK."
        ),
        cwd=str(ROOT),
        scout_areas=["No scouting required for this E2E marker test."],
        implementation_items=[],
        sandbox="read-only",
        max_workers=1,
        session_context=SESSION_CONTEXT,
        steer_idle_seconds=5,
    )
    run_dir = _run_dir(result)
    _wait_completed(run_dir, ["E2E_FIRSTMATE_OK"], timeout_s=300)
    return {"run_dir": str(run_dir), "thread_id": _thread_id(run_dir)}


def case_claude_advisor() -> dict[str, Any]:
    result = bridge.start_visible_claude_advisor(
        prompt="Self-contained advisor E2E. Reply exactly E2E_CLAUDE_ADVISOR_OK.",
        cwd=str(ROOT),
        title="E2E Claude advisor",
        max_budget_usd="0.10",
        session_context=SESSION_CONTEXT,
    )
    run_dir = _run_dir(result)
    _wait_completed(run_dir, ["E2E_CLAUDE_ADVISOR_OK"], timeout_s=240)
    assert (run_dir / "session_id.txt").exists(), run_dir
    return {"run_dir": str(run_dir), "session_id": (run_dir / "session_id.txt").read_text(encoding="utf-8-sig").strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-expensive", action="store_true", help="Skip Haiku, first-mate, and Claude advisor cases.")
    args = parser.parse_args()

    results: dict[str, Any] = {}
    print("[0/11] advisor model policy", flush=True)
    _assert_model_policy()

    print("[1/11] Codex MCP tool allowlists", flush=True)
    _assert_codex_mcp_tool_allowlists()

    print("[2/11] captain help mailbox", flush=True)
    results["captain_help"] = case_captain_help_mailbox()
    print(json.dumps(results["captain_help"], indent=2), flush=True)

    print("[3/11] deprecated interactive TUI sidecar dry-run", flush=True)
    results["interactive_tui"] = case_interactive_tui_sidecar_dry_run()
    print(json.dumps(results["interactive_tui"], indent=2), flush=True)

    print("[4/11] deprecated interactive first-mate TUI dry-run", flush=True)
    results["interactive_firstmate_tui"] = case_interactive_first_mate_tui_dry_run()
    print(json.dumps(results["interactive_firstmate_tui"], indent=2), flush=True)

    print("[5/11] visible worker + queued steer", flush=True)
    results["queued"] = case_visible_worker_and_queued_steer()
    print(json.dumps(results["queued"], indent=2), flush=True)

    print("[6/11] closed run resume + permission override", flush=True)
    results["resume"] = case_closed_run_resume(results["queued"])
    print(json.dumps(results["resume"], indent=2), flush=True)

    print("[7/11] interrupt current turn + resume steering", flush=True)
    results["interrupt"] = case_interrupt_steering()
    print(json.dumps(results["interrupt"], indent=2), flush=True)

    print("[8/11] mandatory supervision review cycle", flush=True)
    results["supervision"] = case_supervision_review_cycle()
    print(json.dumps(results["supervision"], indent=2), flush=True)

    if not args.skip_expensive:
        print("[9/11] Haiku-composed Codex worker", flush=True)
        results["haiku"] = case_haiku_composed_worker()
        print(json.dumps(results["haiku"], indent=2), flush=True)

        print("[10/11] first-mate visible pool", flush=True)
        results["firstmate"] = case_first_mate_pool()
        print(json.dumps(results["firstmate"], indent=2), flush=True)

        print("[11/11] Claude advisor visible run", flush=True)
        results["claude_advisor"] = case_claude_advisor()
        print(json.dumps(results["claude_advisor"], indent=2), flush=True)

    _assert_no_git_changes()
    print(json.dumps({"ok": True, "results": results}, indent=2), flush=True)


if __name__ == "__main__":
    main()
