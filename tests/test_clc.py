"""E2E for clc / Cursor Cloud Agents API.

Run from the repo root:
  python tests/test_clc.py

Requires ~/.cc-bridge/secrets/cursor-api.key or CURSOR_API_KEY.
Does not create a new cloud agent unless --create-cloud is passed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cursor_cloud_api as api  # noqa: E402


def _ok(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    extra = f" {detail}" if detail else ""
    print(f"{status}  {name}{extra}")
    if not cond:
        raise SystemExit(1)


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
        _ok("POST /v1/messages 404", False, "unexpected success (Claude Code dialect would work)")
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


def test_launcher_help() -> None:
    ps1 = Path.home() / "bin" / "clc.ps1"
    _ok("deployed ~/bin/clc.ps1", ps1.is_file(), str(ps1))
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps1),
        "--help",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    out = (proc.stdout or "") + (proc.stderr or "")
    _ok("clc --help mentions Cloud Agents", "Cloud Agent" in out or "api.cursor.com" in out, f"exit={proc.returncode}")
    _ok("clc --help exit 0", proc.returncode == 0, out[-300:])


def test_clc_me() -> None:
    ps1 = Path.home() / "bin" / "clc.ps1"
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), "--me"],
        capture_output=True,
        text=True,
        timeout=40,
    )
    _ok("clc --me exit 0", proc.returncode == 0, (proc.stderr or "")[-200:])
    data = json.loads(proc.stdout)
    _ok("clc --me has apiKeyName", bool(data.get("apiKeyName")), json.dumps(data)[:200])


def test_local_print(prompt: str = "Reply with only the token E2E_CLC_LOCAL_OK and nothing else.") -> None:
    ps1 = Path.home() / "bin" / "clc.ps1"
    proc = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
            "-p",
            prompt,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    _ok("clc -p exit 0", proc.returncode == 0, out[-400:])
    _ok("clc -p contains E2E_CLC_LOCAL_OK", "E2E_CLC_LOCAL_OK" in out, out[-400:])


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
    skip_local = "--skip-local" in sys.argv
    print("clc e2e")
    test_messages_still_404()
    test_me_and_list()
    test_launcher_help()
    test_clc_me()
    if not skip_local:
        test_local_print()
    else:
        print("SKIP  clc -p ( --skip-local )")
    if create_cloud:
        test_cloud_followup()
    else:
        print("SKIP  cloud followup (pass --create-cloud to run)")
    print("ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
