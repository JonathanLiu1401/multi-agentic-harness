"""E2E for clc: Cursor Anthropic translator + Cloud Agents API.

Run from the repo root:
  python tests/test_clc.py

Requires ~/.cc-bridge/secrets/cursor-api.key or CURSOR_API_KEY.
Does not launch the Claude Code TUI. Does not create a new cloud agent
unless --create-cloud is passed.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "gateway"))
import cursor_cloud_api as api  # noqa: E402
import clc_pricing  # noqa: E402
from cursor_anthropic_gateway import anthropic_usage  # noqa: E402
from types import SimpleNamespace
TEMPLATE = ROOT / "templates" / "claude-clc" / "settings.json"

GATEWAY = os.environ.get("CLC_GATEWAY", "http://127.0.0.1:8318")
LAUNCHER = Path.home() / "bin" / "clc.ps1"
REPO_LAUNCHER = ROOT / "launchers" / "clc.ps1"


def _ok(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    extra = f" {detail}" if detail else ""
    print(f"{status}  {name}{extra}")
    if not cond:
        raise SystemExit(1)


def test_pricing_covers_every_picker_id() -> None:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    picker = set(data.get("availableModels") or [])
    overrides = set((data.get("modelPricing") or {}).get("overrides") or {})
    rates = set(clc_pricing.RATES)
    _ok("every picker id has a rate", picker <= overrides, f"missing={sorted(picker - overrides)}")
    _ok("canonical table matches settings.json", rates == overrides)
    opus = data["modelPricing"]["overrides"]["claude-opus-5"]
    _ok("Opus 5 is $5/$25 not $15/$75", opus["input"] == 5.0 and opus["output"] == 25.0)
    mini = data["modelPricing"]["overrides"]["gpt-5.4-mini"]
    _ok("GPT-5.4 mini is not GPT-5.5 rates", mini["input"] == 0.75 and mini["output"] == 4.5)


def test_anthropic_usage_mapping() -> None:
    mapped = anthropic_usage(
        SimpleNamespace(input_tokens=1200, output_tokens=80, cache_read_tokens=400, cache_write_tokens=50)
    )
    _ok("usage maps cache fields", mapped == {
        "input_tokens": 1200,
        "output_tokens": 80,
        "cache_read_input_tokens": 400,
        "cache_creation_input_tokens": 50,
    })
    _ok("empty usage is omitted", anthropic_usage(SimpleNamespace(input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0)) is None)


def test_messages_still_404() -> None:
    key = api.load_key()
    req = urllib.request.Request(
        "https://api.cursor.com/v1/messages",
        data=b'{"model":"auto","max_tokens":8,"messages":[{"role":"user","content":"ping"}]}',
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=20)
        _ok("POST /v1/messages 404", False, "unexpected success (Cursor still has no Anthropic API)")
    except urllib.error.HTTPError as exc:
        _ok("POST /v1/messages 404", exc.code == 404, f"status={exc.code}")


def test_me_and_list() -> None:
    me = api.get_me()
    _ok("GET /v1/me", bool(me.get("apiKeyName") or me.get("userEmail")), json.dumps(me)[:200])
    models = api.list_models()
    ids = [item.get("id") for item in models.get("items") or []]
    _ok("GET /v1/models has grok-4.6", "grok-4.6" in ids, f"n={len(ids)}")
    agents = api.list_agents(limit=5)
    _ok("GET /v1/agents", "items" in agents, f"n={len(agents.get('items') or [])}")


def test_launcher_is_claude_code_dialect() -> None:
    src = REPO_LAUNCHER.read_text(encoding="utf-8")
    _ok("clc.ps1 points at :8318", "127.0.0.1:8318" in src)
    _ok("clc.ps1 sets CLAUDE_CONFIG_DIR", ".claude-clc" in src)
    _ok(
        "clc.ps1 does not pin CLAUDE_CODE_EFFORT_LEVEL",
        "CLAUDE_CODE_EFFORT_LEVEL =" not in src
        and "Remove-Item -Path Env:CLAUDE_CODE_EFFORT_LEVEL" in src,
    )
    _ok("clc.ps1 does not exec cursor-agent", "cursor-agent" not in src.lower())
    _ok("deployed ~/bin/clc.ps1", LAUNCHER.is_file(), str(LAUNCHER))


def test_translator_health() -> None:
    req = urllib.request.Request(f"{GATEWAY}/health", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            _ok("GET :8318/health", resp.status == 200, body[:200])
    except Exception as exc:
        _ok("GET :8318/health", False, str(exc))


def test_cloud_followup() -> None:
    agents = api.list_agents(limit=5).get("items") or []
    if not agents:
        print("SKIP  cloud followup (no existing agents)")
        return
    agent_id = agents[0]["id"]
    created = api.create_run(
        agent_id,
        "Reply with only the token E2E_CLC_CLOUD_OK and then stop. Do not edit files.",
    )
    run = created.get("run") or created
    run_id = run.get("id")
    _ok("POST /v1/agents/{id}/runs", bool(run_id), json.dumps(created)[:300])
    finished = api.wait_run(agent_id, run_id, timeout_s=240.0)
    result = str(finished.get("result") or "")
    status = str(finished.get("status") or "")
    _ok(
        "cloud run finished with E2E_CLC_CLOUD_OK",
        status.upper() == "FINISHED" and "E2E_CLC_CLOUD_OK" in result,
        f"status={status} result={result[:240]}",
    )


def main() -> int:
    create_cloud = "--create-cloud" in sys.argv
    skip_health = "--skip-health" in sys.argv
    print("clc e2e")
    test_pricing_covers_every_picker_id()
    test_anthropic_usage_mapping()
    test_messages_still_404()
    test_me_and_list()
    test_launcher_is_claude_code_dialect()
    if skip_health:
        print("SKIP  translator health ( --skip-health )")
    else:
        test_translator_health()
    if create_cloud:
        test_cloud_followup()
    else:
        print("SKIP  cloud followup (pass --create-cloud to run)")
    print("ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
