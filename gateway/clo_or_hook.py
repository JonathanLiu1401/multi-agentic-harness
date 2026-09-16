"""UserPromptSubmit hook: /or <query> searches OpenRouter without an LLM call."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from refresh_clo_models import fetch_catalog, print_search, _read_key
except ImportError:
    sys.path.insert(0, str(Path.home() / ".cc-bridge"))
    from refresh_clo_models import fetch_catalog, print_search, _read_key  # type: ignore


def _query(payload: dict) -> str | None:
    prompt = str(payload.get("prompt") or "").strip()
    if prompt.lower().startswith("/or"):
        rest = prompt[3:].strip()
        return rest
    cmd = str(payload.get("command") or payload.get("slash_command") or "").strip().lower()
    if cmd in ("or", "/or"):
        return str(payload.get("command_args") or payload.get("arguments") or "").strip()
    return None


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    query = _query(payload)
    if query is None:
        return 0
    if not query:
        msg = "usage: /or <query>   example: /or nemotron"
        json.dump({"continue": False, "systemMessage": msg}, sys.stdout)
        return 0
    key = _read_key()
    if not key:
        json.dump(
            {"continue": False, "systemMessage": "clo: no OpenRouter key in ~/.cc-bridge/secrets/openrouter-api.key"},
            sys.stdout,
        )
        return 0
    try:
        catalog = fetch_catalog(key)
    except Exception as exc:
        json.dump(
            {"continue": False, "systemMessage": f"clo: catalog fetch failed ({exc.__class__.__name__})"},
            sys.stdout,
        )
        return 0
    from io import StringIO

    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        print_search(query, catalog)
    finally:
        sys.stdout = old
    text = buf.getvalue().rstrip() or f"clo: no matches for {query!r}"
    json.dump(
        {
            "continue": False,
            "stopReason": text,
            "systemMessage": text,
            "suppressOutput": False,
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
