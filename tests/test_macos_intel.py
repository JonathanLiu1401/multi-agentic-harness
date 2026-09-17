"""Intel macOS path/launch contracts for the visible-agent bridge."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _bridge():
    spec = importlib.util.spec_from_file_location(
        "bridge_macos_under_test", REPO / "visible_agent_bridge.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["bridge_macos_under_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bridge():
    return _bridge()


def test_grok_cli_is_not_the_windows_hardcode(bridge):
    grok = bridge._grok_cli()
    assert "C:\\Users\\jonny" not in str(grok)
    if sys.platform == "darwin":
        assert grok.exists(), f"grok CLI missing at {grok} on this Mac"
        assert grok.name == "grok"


def test_agy_cli_is_not_the_windows_hardcode(bridge):
    agy = bridge._agy_cli()
    assert "AppData" not in str(agy)


def test_posix_grok_run_uses_python_runner(bridge, tmp_path):
    (tmp_path / "metadata.json").write_text('{"agent": "grok"}\n', encoding="utf-8")
    runner = bridge._posix_python_runner_for(tmp_path)
    assert runner is not None
    assert runner.name == "grok_worker_runner.py"
    assert runner.is_file()


def test_launch_on_posix_does_not_call_powershell(bridge, tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("posix launch path")
    (tmp_path / "metadata.json").write_text('{"agent": "grok"}\n', encoding="utf-8")
    seen = {}

    def fake_visible(script_path, run_dir, env=None):
        seen["script"] = Path(script_path)
        seen["run_dir"] = Path(run_dir)
        return 4242

    monkeypatch.setattr(bridge, "_launch_visible_python", fake_visible)
    pid = bridge._launch_posix_script(tmp_path / "run.ps1")
    assert pid == 4242
    assert seen["script"].name == "grok_worker_runner.py"
    assert seen["run_dir"] == tmp_path


def test_grok_worker_runner_argv_uses_prompt_file(tmp_path):
    sys.path.insert(0, str(REPO))
    import grok_worker_runner as runner

    meta = {
        "cwd": str(tmp_path),
        "model": "grok-4.6",
        "requested_sandbox": "read-only",
        "requested_reasoning_effort": "high",
        "grok_cli": "/usr/bin/env",
    }
    (tmp_path / "metadata.json").write_text(__import__("json").dumps(meta), encoding="utf-8")
    (tmp_path / "prompt.md").write_text("hi\n", encoding="utf-8")
    run = runner.Run(tmp_path)
    args = run._grok_args(tmp_path / "prompt.md", "", "initial")
    assert "--prompt-file" in args
    assert "-p" not in args
    assert "--output-format" in args and "streaming-json" in args
    assert "--disallowed-tools" in args
    assert "--reasoning-effort" in args
    assert "high" in args
