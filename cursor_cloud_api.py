"""Cursor Cloud Agents API client (stdlib only).

Used by the `clc` launcher and by agent-visibility MCP tools.
Auth: Basic (API key as username, empty password) or Bearer.
Key file: ~/.cc-bridge/secrets/cursor-api.key  (CURSOR_API_KEY env wins).

This is NOT an Anthropic/OpenAI inference API. POST /v1/messages and
POST /v1/chat/completions 404. Cloud Agents are fire-and-forget coding
agents (prompt -> VM tools -> result), inverted from Claude Code's loop.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://api.cursor.com"
KEY_FILE = Path.home() / ".cc-bridge" / "secrets" / "cursor-api.key"


class CursorCloudError(RuntimeError):
    def __init__(self, status: int, payload: Any, path: str) -> None:
        self.status = status
        self.payload = payload
        self.path = path
        super().__init__(f"Cursor Cloud API {status} {path}: {payload}")


def load_key() -> str:
    env = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if env:
        return env
    if KEY_FILE.is_file():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    raise CursorCloudError(
        0,
        f"missing CURSOR_API_KEY and {KEY_FILE}",
        "/auth",
    )


def request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> tuple[int, Any]:
    key = load_key()
    url = API_BASE + path
    if query:
        filtered = {k: v for k, v in query.items() if v is not None and v != ""}
        if filtered:
            url += "?" + urllib.parse.urlencode(filtered)
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method.upper())
    token = base64.b64encode(f"{key}:".encode("ascii")).decode("ascii")
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            payload: Any = json.loads(raw) if raw.strip() else {}
            return int(resp.status), payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw.strip() else {"error": raw}
        except json.JSONDecodeError:
            payload = {"error": raw}
        return int(exc.code), payload
    except urllib.error.URLError as exc:
        raise CursorCloudError(0, str(exc.reason), path) from exc


def _ok(status: int, payload: Any, path: str) -> Any:
    if status >= 400:
        raise CursorCloudError(status, payload, path)
    return payload


def get_me() -> Any:
    status, payload = request("GET", "/v1/me")
    return _ok(status, payload, "/v1/me")


def list_agents(limit: int = 20, cursor: str = "", include_archived: bool = False) -> Any:
    q: dict[str, Any] = {"limit": str(limit)}
    if cursor:
        q["cursor"] = cursor
    if include_archived:
        q["includeArchived"] = "true"
    status, payload = request("GET", "/v1/agents", query=q)
    return _ok(status, payload, "/v1/agents")


def list_models() -> Any:
    status, payload = request("GET", "/v1/models")
    return _ok(status, payload, "/v1/models")


def get_agent(agent_id: str) -> Any:
    path = f"/v1/agents/{agent_id}"
    status, payload = request("GET", path)
    return _ok(status, payload, path)


def create_agent(
    prompt: str,
    model: str = "",
    repo_url: str = "",
    starting_ref: str = "main",
    name: str = "",
    auto_create_pr: bool = False,
) -> Any:
    body: dict[str, Any] = {"prompt": {"text": prompt}}
    if model:
        body["model"] = {"id": model}
    if name:
        body["name"] = name
    if repo_url:
        repo: dict[str, Any] = {"url": repo_url}
        if starting_ref:
            repo["startingRef"] = starting_ref
        body["repos"] = [repo]
    if auto_create_pr:
        body["autoCreatePR"] = True
    status, payload = request("POST", "/v1/agents", body=body)
    return _ok(status, payload, "/v1/agents")


def create_run(agent_id: str, prompt: str, mode: str = "") -> Any:
    body: dict[str, Any] = {"prompt": {"text": prompt}}
    if mode:
        body["mode"] = mode
    path = f"/v1/agents/{agent_id}/runs"
    status, payload = request("POST", path, body=body)
    return _ok(status, payload, path)


def get_run(agent_id: str, run_id: str) -> Any:
    path = f"/v1/agents/{agent_id}/runs/{run_id}"
    status, payload = request("GET", path)
    return _ok(status, payload, path)


def wait_run(
    agent_id: str,
    run_id: str,
    timeout_s: float = 300.0,
    poll_s: float = 4.0,
) -> Any:
    deadline = time.time() + timeout_s
    last: Any = None
    while time.time() < deadline:
        last = get_run(agent_id, run_id)
        status = str((last or {}).get("status") or "").upper()
        if status in ("FINISHED", "ERROR", "CANCELLED", "CANCELED", "FAILED"):
            return last
        time.sleep(poll_s)
    raise CursorCloudError(0, {"timeout": True, "last": last}, f"/v1/agents/{agent_id}/runs/{run_id}")


def key_file_present() -> bool:
    return bool((os.environ.get("CURSOR_API_KEY") or "").strip()) or KEY_FILE.is_file()


def _print(obj: Any) -> int:
    json.dump(obj, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cursor_cloud_api", description="Cursor Cloud Agents API")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("me")
    p_list = sub.add_parser("list")
    p_list.add_argument("--limit", type=int, default=20)
    sub.add_parser("models")
    p_get = sub.add_parser("get")
    p_get.add_argument("agent_id")
    p_create = sub.add_parser("create")
    p_create.add_argument("--prompt", required=True)
    p_create.add_argument("--model", default="")
    p_create.add_argument("--repo", default="")
    p_create.add_argument("--ref", default="main")
    p_create.add_argument("--name", default="")
    p_create.add_argument("--auto-pr", action="store_true")
    p_run = sub.add_parser("run")
    p_run.add_argument("agent_id")
    p_run.add_argument("--prompt", required=True)
    p_run.add_argument("--mode", default="")
    p_wait = sub.add_parser("wait")
    p_wait.add_argument("agent_id")
    p_wait.add_argument("run_id")
    p_wait.add_argument("--timeout", type=float, default=300.0)
    p_get_run = sub.add_parser("get-run")
    p_get_run.add_argument("agent_id")
    p_get_run.add_argument("run_id")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "me":
            return _print(get_me())
        if args.cmd == "list":
            return _print(list_agents(limit=args.limit))
        if args.cmd == "models":
            return _print(list_models())
        if args.cmd == "get":
            return _print(get_agent(args.agent_id))
        if args.cmd == "create":
            return _print(create_agent(
                prompt=args.prompt,
                model=args.model,
                repo_url=args.repo,
                starting_ref=args.ref,
                name=args.name,
                auto_create_pr=args.auto_pr,
            ))
        if args.cmd == "run":
            return _print(create_run(args.agent_id, args.prompt, mode=args.mode))
        if args.cmd == "get-run":
            return _print(get_run(args.agent_id, args.run_id))
        if args.cmd == "wait":
            return _print(wait_run(args.agent_id, args.run_id, timeout_s=args.timeout))
    except CursorCloudError as exc:
        json.dump({"ok": False, "status": exc.status, "path": exc.path, "error": exc.payload}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1
    parser.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
