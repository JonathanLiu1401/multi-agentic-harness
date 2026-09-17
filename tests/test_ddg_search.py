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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("All DuckDuckGo search tests passed.")
