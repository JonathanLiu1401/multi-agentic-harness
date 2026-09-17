"""DuckDuckGo Search MCP Server for Claude Code (clo / free web search).

Provides web search via the maintained `ddgs` library. No API keys and no
OpenRouter server-side search plugin fees.

Requires: py -3 -m pip install ddgs

The previous implementation scraped lite.duckduckgo.com directly. That stopped
working because DuckDuckGo serves an anti-bot challenge (HTTP 202) to plain
urllib requests, so every query silently returned zero results.
"""
from __future__ import annotations

import html
import re

from ddgs import DDGS

try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.mcpserver import MCPServer as FastMCP
    except (ImportError, ModuleNotFoundError):
        from fastmcp import FastMCP

mcp = FastMCP("duckduckgo")


def _clean_text(s: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", s).strip()
    cleaned = html.unescape(cleaned)
    # Project rule: no em/en dashes (they corrupt PS 5.1 reads of BOM-less files).
    cleaned = cleaned.replace("—", " - ").replace("–", " - ")
    return " ".join(cleaned.split())


def _execute_search(query: str, max_results: int = 8) -> list[dict[str, str]]:
    rows = DDGS().text(query, max_results=max_results)
    results: list[dict[str, str]] = []
    for row in rows:
        url = (row.get("href") or "").strip()
        if not url:
            continue
        results.append(
            {
                "title": _clean_text(row.get("title") or ""),
                "url": url,
                "snippet": _clean_text(row.get("body") or ""),
            }
        )
        if len(results) >= max_results:
            break
    return results


@mcp.tool()
def duckduckgo_search(query: str, max_results: int = 8) -> str:
    """Search the web using DuckDuckGo for free (no API keys, zero token fees).

    Args:
        query: The search query string.
        max_results: Max number of results (default 8).

    Returns:
        Formatted list of web search results with title, URL, and snippet.
    """
    if not query or not query.strip():
        return "Error: query is empty."
    try:
        results = _execute_search(query.strip(), max_results=max_results)
    except Exception as err:
        return f"DuckDuckGo search error: {type(err).__name__}: {err}"
    if not results:
        return f'No DuckDuckGo results found for query: "{query}"'
    formatted = [
        f"{i}. [{r['title']}]({r['url']})\n   {r['snippet']}"
        for i, r in enumerate(results, 1)
    ]
    return "\n\n".join(formatted)


@mcp.tool()
def web_search(query: str, max_results: int = 8) -> str:
    """Search the web using DuckDuckGo for free (alias for duckduckgo_search).

    Args:
        query: The search query string.
        max_results: Max number of results (default 8).

    Returns:
        Formatted list of web search results with title, URL, and snippet.
    """
    return duckduckgo_search(query=query, max_results=max_results)


if __name__ == "__main__":
    mcp.run()
