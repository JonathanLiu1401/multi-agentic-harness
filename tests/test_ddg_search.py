"""Tests for DuckDuckGo MCP search server (free clo search).

These assert real results. The previous version accepted "No DuckDuckGo
results" and "error" as passing, so it stayed green while search was
completely broken.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gateway.ddg_search_server import (  # noqa: E402
    _clean_text,
    _execute_search,
    duckduckgo_search,
    web_search,
)


def test_clean_text() -> None:
    cleaned = _clean_text("<b>Hello</b> &amp; world &mdash; test")
    assert "<b>" not in cleaned
    assert "&amp;" not in cleaned
    assert "—" not in cleaned
    assert "Hello & world - test" in cleaned


def test_execute_search_returns_real_rows() -> None:
    rows = _execute_search("Analog Devices ADIS16507 datasheet", max_results=4)
    assert rows, "search returned no rows; DuckDuckGo backend is broken"
    assert len(rows) <= 4
    for row in rows:
        assert row["url"].startswith("http"), f"bad url: {row['url']!r}"
    assert any("analog.com" in row["url"] for row in rows), (
        "expected at least one analog.com hit for a part-number query"
    )


def _assert_real_results(res: str) -> None:
    # Match the failure prefixes exactly; "error" also occurs in real snippets.
    assert not res.startswith("DuckDuckGo search error:"), res[:200]
    assert not res.startswith("No DuckDuckGo results"), res[:200]
    assert re.search(r"\[.*\]\(https?://", res), f"unformatted output: {res[:200]!r}"


def test_duckduckgo_search_formats_results() -> None:
    res = duckduckgo_search("OpenRouter AI", max_results=3)
    _assert_real_results(res)
    assert res.startswith("1. ["), f"missing numbering: {res[:80]!r}"


def test_web_search_alias() -> None:
    _assert_real_results(web_search("Python programming language", max_results=2))


def test_empty_query_rejected() -> None:
    assert duckduckgo_search("   ") == "Error: query is empty."


def test_apply_puts_union_alpha_first() -> None:
    from gateway.refresh_clo_models import apply

    settings: dict = {}
    available = ["aion-labs/aion-2.0[1m]", "stealth/union-alpha[1m]"]
    apply(settings, available, [{"model": m} for m in available], {}, "stealth/union-alpha[1m]")
    assert settings["model"] == "stealth/union-alpha[1m]"
    assert settings["availableModels"][0] == "stealth/union-alpha[1m]"


def test_clo_default_is_union_alpha() -> None:
    from gateway.refresh_clo_models import _pick_default

    available = [
        "openai/gpt-5.6-sol[1m]",
        "stealth/union-alpha[1m]",
        "~anthropic/claude-sonnet-latest[1m]",
    ]
    assert _pick_default(available, None) == "stealth/union-alpha[1m]"
    assert _pick_default(available, "~anthropic/claude-sonnet-latest[1m]") == "stealth/union-alpha[1m]"
    assert _pick_default(available, "openai/gpt-5.6-sol[1m]") == "openai/gpt-5.6-sol[1m]"


def test_clo_python_is_not_frameworks_37() -> None:
    """Intel Mac PATH python3 is often python.org 3.7; clo MCP must not use it."""
    from gateway.refresh_clo_models import _clo_python, _ensure_duckduckgo_mcp

    py = _clo_python()
    assert "Python.framework/Versions/3.7" not in py
    settings: dict = {}
    _ensure_duckduckgo_mcp(settings)
    entry = settings["mcpServers"]["duckduckgo"]
    if sys.platform != "win32":
        assert entry["command"] == py
        assert not entry["command"].endswith("/python3") or "3.7" not in entry["command"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("All DuckDuckGo search tests passed.")
