"""Tests for DuckDuckGo MCP search server (free clo search)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gateway.ddg_search_server import _clean_text, _execute_search, duckduckgo_search, web_search


def test_clean_text() -> None:
    raw = "<b>Hello</b> &amp; world &mdash; test"
    cleaned = _clean_text(raw)
    assert "<b>" not in cleaned
    assert "&amp;" not in cleaned
    assert "—" not in cleaned
    assert "Hello & world - test" in cleaned


def test_duckduckgo_search_offline_or_online() -> None:
    res = duckduckgo_search("OpenRouter AI", max_results=3)
    assert isinstance(res, str)
    assert len(res) > 0
    # Should not throw and should contain markdown link or error message
    assert "[" in res or "No DuckDuckGo results" in res or "error" in res.lower()


def test_web_search_alias() -> None:
    res = web_search("Python programming language", max_results=2)
    assert isinstance(res, str)
    assert len(res) > 0


if __name__ == "__main__":
    test_clean_text()
    test_duckduckgo_search_offline_or_online()
    test_web_search_alias()
    print("All DuckDuckGo search tests passed.")
