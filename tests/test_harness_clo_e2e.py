"""End-to-End Test for Claude Code Harnesses (focusing on CLO with NVIDIA Nemotron 3.5 Lightning).

Tests all features of /claude-manages-codex with Claude Code provider harnesses:
1. Backend checks for all harnesses (clo, clx, clg, cld, clc, claude)
2. Live worker execution with harness="clo" and model="nvidia/nemotron-3.5-lightning:free[1m]"
3. Status tracking and session persistence
4. Captain Mailbox: request_captain_help, list_captain_help_requests, respond_to_captain_help_request
5. Active steering: steer_claude_run, queue pickup, resume turn execution, steer_done
6. Captain Reports: submit_captain_report, list_captain_reports, final.json validation
7. First-mate pool & visible worker helpers
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import visible_agent_bridge as bridge


def _ok(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    extra = f" ({detail})" if detail else ""
    print(f"[{status}] {name}{extra}")
    if not cond:
        raise AssertionError(f"Check failed: {name} - {detail}")


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    return default


def test_backends_availability() -> None:
    print("\n--- Testing Backend Availability ---")
    backends = bridge.check_worker_backends()
    for h in ["harness_clo", "harness_clx", "harness_clg", "harness_cld", "harness_clc", "harness_claude"]:
        info = backends.get(h, {})
        _ok(f"backend {h} available", info.get("available") is True, info.get("reason", ""))


def test_harness_config_resolution() -> None:
    print("\n--- Testing Harness Config Resolution ---")
    harnesses = ["clo", "clx", "clg", "cld", "clc", "claude"]
    for h in harnesses:
        cfg = bridge._resolve_harness_config(h)
        _ok(f"harness config {h} resolved", cfg["harness"] == h, f"model={cfg['model']}")
        _ok(f"harness {h} has config_dir", bool(cfg.get("config_dir")), cfg.get("config_dir", ""))
        _ok(f"harness {h} has env dict", isinstance(cfg.get("env"), dict))

    # Test custom model override
    custom = bridge._resolve_harness_config("clo", "nvidia/nemotron-3.5-lightning:free[1m]")
    _ok("custom model override preserved", custom["model"] == "nvidia/nemotron-3.5-lightning:free[1m]")
    _ok("openrouter base_url set", custom["env"].get("ANTHROPIC_BASE_URL") == "https://openrouter.ai/api")


def test_live_clo_nemotron_worker_and_features() -> None:
    print("\n--- Testing Live CLO Worker with Nemotron 3.5 Lightning ---")
    cwd = str(ROOT)
    test_title = "E2E CLO Nemotron Test Worker"
    test_prompt = (
        "You are an automated test worker running in the multi-agentic harness. "
        "State that you are ready and include the exact marker: E2E_NEMOTRON_INITIAL_OK."
    )

    result = bridge.start_claude_worker(
        prompt=test_prompt,
        cwd=cwd,
        title=test_title,
        model="nvidia/nemotron-3.5-lightning:free[1m]",
        harness="clo",
        sandbox="read-only",
        steer_idle_seconds=45,
        visible=False,
    )

    run_dir = Path(result["run_dir"])
    _ok("worker spawned with run_dir", run_dir.exists(), str(run_dir))
    _ok("launcher_pid recorded", (run_dir / "launcher_pid.txt").exists())

    meta = _read_json(run_dir / "metadata.json", {})
    _ok("metadata records harness=clo", meta.get("harness") == "clo")
    _ok("metadata records requested model", meta.get("model") == "nvidia/nemotron-3.5-lightning:free[1m]")
    _ok("metadata read-only enforced", meta.get("read_only_enforced") is True)

    print("Waiting for initial Nemotron turn to complete (polling status)...")
    # Nemotron free tier with thinking tokens takes ~40-70 seconds
    deadline = time.time() + 150
    initial_completed = False
    while time.time() < deadline:
        status_data = _read_json(run_dir / "status.json", {})
        st = status_data.get("status", "")
        if st in ("waiting_for_steer", "completed"):
            initial_completed = True
            print(f"Initial turn completed with status: {st}")
            break
        elif "failed" in st:
            print(f"Run failed: {st}")
            break
        time.sleep(3)

    _ok("initial turn reached waiting_for_steer or completed", initial_completed)

    session_id = (run_dir / "session_id.txt").read_text(encoding="utf-8").strip() if (run_dir / "session_id.txt").exists() else ""
    _ok("session_id captured from Claude Code stream", bool(session_id), session_id)

    final_json = run_dir / "captain_reports" / "final.json"
    _ok("auto captain report generated", final_json.exists())
    if final_json.exists():
        rep_data = _read_json(final_json, {})
        _ok("captain report has summary", bool(rep_data.get("summary")))

    # Test list_captain_reports
    reports = bridge.list_captain_reports(run_dir=str(run_dir))
    _ok("list_captain_reports returns report", len(reports) > 0)

    # -----------------------------------------------------------------------
    # Captain Mailbox Help Request Test
    # -----------------------------------------------------------------------
    print("\n--- Testing Captain Mailbox: Help Request & Response ---")
    help_req = bridge.request_captain_help(
        run_dir=str(run_dir),
        question="Need captain advice on test validation.",
        context="E2E testing of clo harness with Nemotron.",
        urgency="normal",
        recommended_next="Approve and proceed with steering turn.",
    )
    _ok("request_captain_help succeeded", help_req.get("ok") is True)
    req_id = help_req.get("request_id", "")

    # List help requests
    pending = bridge.list_captain_help_requests(run_dir=str(run_dir))
    _ok("list_captain_help_requests sees pending request", any(r["request_id"] == req_id for r in pending))

    # Respond to captain help request
    help_resp = bridge.respond_to_captain_help_request(
        run_dir=str(run_dir),
        request_id=req_id,
        response="Captain approval granted. Output marker E2E_NEMOTRON_STEER_OK.",
        sandbox="read-only",
        launch_if_closed=True,
    )
    _ok("respond_to_captain_help_request succeeded", help_resp.get("ok") is True)

    # Verify pending requests are now 0
    pending_after = bridge.list_captain_help_requests(run_dir=str(run_dir))
    _ok("pending help requests cleared", len(pending_after) == 0)

    # -----------------------------------------------------------------------
    # Active Steering Test
    # -----------------------------------------------------------------------
    print("\n--- Testing Active Steering Execution ---")
    # Also queue an explicit steering instruction to verify steer_claude_run
    steer_result = bridge.steer_claude_run(
        run_dir=str(run_dir),
        instruction="Steering instruction: confirm reception and output exact marker E2E_STEERING_COMPLETE.",
        sandbox="read-only",
        launch_if_closed=True,
    )
    _ok("steer_claude_run queued", steer_result.get("ok") is True, steer_result.get("mode", ""))

    print("Waiting for steer turn to be picked up and executed...")
    steer_deadline = time.time() + 150
    steer_completed = False
    while time.time() < steer_deadline:
        # Check if steer_queue has been processed into steer_done
        steer_done_files = list((run_dir / "steer_done").glob("*.md"))
        status_data = _read_json(run_dir / "status.json", {})
        st = status_data.get("status", "")
        if steer_done_files and st in ("waiting_for_steer", "completed"):
            steer_completed = True
            print(f"Steer turn finished; status: {st}, processed steers: {len(steer_done_files)}")
            break
        time.sleep(3)

    _ok("steering turn executed and moved to steer_done", steer_completed)

    # -----------------------------------------------------------------------
    # Submit Captain Report Test
    # -----------------------------------------------------------------------
    print("\n--- Testing Submit Captain Report ---")
    sub_res = bridge.submit_captain_report(
        run_dir=str(run_dir),
        outcome="completed",
        summary="All Nemotron E2E verification points succeeded.",
        changed_files=[],
        verification=["Backend checks PASS", "Worker turn PASS", "Steering turn PASS", "Mailbox PASS"],
    )
    _ok("submit_captain_report succeeded", sub_res.get("ok") is True)

    final_reports = bridge.list_captain_reports(run_dir=str(run_dir))
    _ok("final report recorded outcome=completed", any(r["outcome"] == "completed" for r in final_reports))

    # Overall run status
    run_status = bridge.get_visible_run_status(str(run_dir))
    _ok("get_visible_run_status retrieves status", run_status.get("status") is not None)


def test_visible_and_pool_helpers() -> None:
    print("\n--- Testing Visible Worker & First Mate Pool Helpers ---")
    cwd = str(ROOT)

    # Test start_visible_first_mate_claude_pool prompt construction
    pool_res = bridge.start_visible_first_mate_claude_pool(
        goal="E2E test pool coordination",
        cwd=cwd,
        scout_areas=["tests", "gateway"],
        implementation_items=["verify bridge"],
        harness="clo",
        model="nvidia/nemotron-3.5-lightning:free[1m]",
        sandbox="read-only",
        visible=False,  # test headless mode here to avoid spawning unwanted windows during CI
    )
    pool_run_dir = Path(pool_res["run_dir"])
    _ok("first mate claude pool spawned", pool_run_dir.exists())
    pool_meta = _read_json(pool_run_dir / "metadata.json", {})
    _ok("pool metadata has harness=clo", pool_meta.get("harness") == "clo")
    _ok("pool prompt contains First Mate contract", "First Mate" in (pool_run_dir / "prompt.md").read_text(encoding="utf-8"))


def main() -> int:
    print("================================================================")
    print("Starting Multi-Agentic Harness E2E Tests (CLO + Nemotron 3.5)")
    print("================================================================")
    t0 = time.time()
    try:
        test_backends_availability()
        test_harness_config_resolution()
        test_live_clo_nemotron_worker_and_features()
        test_visible_and_pool_helpers()
    except Exception as exc:
        print(f"\n[EXCEPTION] Test execution failed: {exc}")
        import traceback
        traceback.print_exc()
        return 1

    elapsed = time.time() - t0
    print("\n================================================================")
    print(f"ALL TESTS PASSED in {elapsed:.1f}s")
    print("================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
