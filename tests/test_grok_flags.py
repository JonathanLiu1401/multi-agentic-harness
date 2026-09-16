"""A grok flag the installed CLI does not know must not reach the command line.

These options are not stable across grok releases. ``--best-of-n`` and
``--check`` were both real when the bridge adopted them and are both gone in
grok 1.0.30. clap does not tolerate an unknown argument: it exits 2 before the
worker ever reads its prompt, so the run dies in well under a second with

    error: unexpected argument '--best-of-n' found

and the auto-report reads "grok turn failed before producing a text answer".
Nothing is written and no work is lost, which is what makes it dangerous in a
parallel fan-out: the fleet comes back one worker short while every sibling
looks healthy, and the captain reports success for an agent that never ran.

So the bridge asks the binary what it supports and drops the rest, saying so in
the window rather than discarding a requested quality lever in silence.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile

import pytest


REPO = Path(__file__).resolve().parents[1]


def _bridge():
    spec = importlib.util.spec_from_file_location(
        "bridge_under_test", REPO / "visible_agent_bridge.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["bridge_under_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bridge():
    return _bridge()


def test_an_unsupported_flag_is_dropped_and_named(bridge, monkeypatch):
    monkeypatch.setattr(
        bridge, "_grok_supported_long_flags", lambda: frozenset({"--reasoning-effort"})
    )
    args, dropped = bridge._grok_initial_extra_args(3, True)
    assert args == [], f"unsupported flags reached the command line: {args}"
    assert dropped == ["--best-of-n", "--check"]


def test_a_supported_flag_survives_with_its_value(bridge, monkeypatch):
    monkeypatch.setattr(
        bridge,
        "_grok_supported_long_flags",
        lambda: frozenset({"--best-of-n", "--check"}),
    )
    args, dropped = bridge._grok_initial_extra_args(3, True)
    assert args == ["--best-of-n", "3", "--check"], args
    assert dropped == []
    # The value must travel with its flag, never orphaned onto the next one.
    assert args[args.index("--best-of-n") + 1] == "3"


def test_asking_for_nothing_probes_nothing(bridge, monkeypatch):
    """The common case must not pay for a subprocess on every launch."""

    def _boom():
        raise AssertionError("probed --help when no extra flags were requested")

    monkeypatch.setattr(bridge, "_grok_supported_long_flags", _boom)
    assert bridge._grok_initial_extra_args(1, False) == ([], [])


def test_an_unreadable_cli_drops_rather_than_risking_the_launch(bridge, monkeypatch):
    """None means the probe failed. Prefer a started worker over a dead one."""

    monkeypatch.setattr(bridge, "_grok_supported_long_flags", lambda: None)
    args, dropped = bridge._grok_initial_extra_args(2, True)
    assert args == []
    assert dropped == ["--best-of-n", "--check"]


def test_the_real_installed_cli_rejects_both_dead_flags(bridge):
    """Against the actual binary on this machine, not a fixture."""

    flags = bridge._grok_supported_long_flags()
    if flags is None:
        pytest.skip("grok CLI not installed or --help unreadable")
    assert "--reasoning-effort" in flags, "probe parsed nothing useful"
    assert "--prompt-file" in flags
    args, dropped = bridge._grok_initial_extra_args(2, True)
    assert args == [], (
        "the installed grok advertises a flag the bridge thought was dead; "
        "re-check the skill's flag list before trusting this"
    )
    assert set(dropped) == {"--best-of-n", "--check"}


def test_the_runner_warns_in_the_window_when_it_drops_a_flag(bridge):
    with tempfile.TemporaryDirectory() as tmp:
        script = bridge._grok_runner(Path(tmp), tmp, "xhigh", best_of_n=2, self_check=True)
    assert "[warn] this grok build does not support" in script
    assert "--best-of-n" in script.split("[warn]")[1].splitlines()[0]
    assert "$InitialExtraArgs = @()" in script, (
        "the dead flags must be absent from the argument array, not merely warned about"
    )


def test_a_clean_run_says_nothing(bridge):
    with tempfile.TemporaryDirectory() as tmp:
        script = bridge._grok_runner(Path(tmp), tmp, "xhigh")
    assert "[warn] this grok build does not support" not in script
