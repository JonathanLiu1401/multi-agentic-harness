"""DuckDuckGo Search MCP Server for Claude Code (clo / free web search).

Provides web search via DuckDuckGo Lite without external API keys or OpenRouter
search plugin fees.
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.mcpserver import MCPServer as FastMCP
    except (ImportError, ModuleNotFoundError):
        from fastmcp import FastMCP

mcp = FastMCP("duckduckgo")


def _clean_text(s: str) -> str:
    cleaned = re.sub(r'<[^>]+>', '', s).strip()
    cleaned = html.unescape(cleaned)
    # Strip em dashes and en dashes to adhere to project rules and prevent PS5.1 encoding issues
    cleaned = (
        cleaned.replace("—", " - ")
        .replace("–", " - ")
        .replace("—", " - ")
        .replace("–", " - ")
    )
    return " ".join(cleaned.split())


def _execute_search(query: str, max_results: int = 8) -> list[dict[str, str]]:
    url = "https://lite.duckduckgo.com/lite/"
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0)"
                " Gecko/20100101 Firefox/128.0"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        page = resp.read().decode("utf-8", errors="replace")

    pattern = re.compile(
        r'<a rel="nofollow" href="([^"]+)" class=[\'"]result-link[\'"]>(.*?)</a>.*?<td class=[\'"]result-snippet[\'"]>(.*?)</td>',
        re.DOTALL,
    )
    results: list[dict[str, str]] = []
    for m in pattern.finditer(page):
        u = m.group(1)
        if "uddg=" in u:
            try:
                parsed = urllib.parse.urlparse(u)
                qs = urllib.parse.parse_qs(parsed.query)
                if "uddg" in qs:
                    u = qs["uddg"][0]
            except Exception:
                pass
        results.append({
            "title": _clean_text(m.group(2)),
            "url": u,
            "snippet": _clean_text(m.group(3)),
        })
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
        if not results:
            return f'No DuckDuckGo results found for query: "{query}"'
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(f"{i}. [{r['title']}]({r['url']})\n   {r['snippet']}")
        return "\n\n".join(formatted)
    except Exception as err:
        return f"DuckDuckGo search error: {err}"


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
