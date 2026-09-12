"""Anthropic /v1/messages front-end for Cursor models.

Claude Code talks to this the same way clx talks to CLIProxyAPI. Cursor's
SDK owns the model loop; Claude Code owns tools. Custom-tool execute()
blocks until the next /v1/messages carries the matching tool_result.

Windows: use AsyncClient.launch_bridge (sync Bridge.launch hits WinError 10038).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import queue
import re
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cursor_sdk import (
    AgentOptions,
    AsyncAgent,
    AsyncClient,
    CustomTool,
    CustomToolContext,
    LocalAgentOptions,
    ModelParameterValue,
    ModelSelection,
    SendOptions,
    TextDeltaUpdate,
    ThinkingDeltaUpdate,
    ToolCallStartedUpdate,
)

HOST = "127.0.0.1"
PORT = 8318
KEY_FILE = Path.home() / ".cc-bridge" / "secrets" / "cursor-api.key"
LOG_FILE = Path.home() / ".cc-bridge" / "clc-gateway.log"

DEFAULT_MODELS = [
    "grok-4.6-fast",
    "grok-4.6",
    "claude-fable-5-1",
    "claude-opus-5-fast",
    "claude-opus-5",
    "gpt-5.6-sol-fast",
    "gpt-5.6-sol",
]

MODEL_ALIASES = {
    "grok": "grok-4.6-fast",
    "grok-4.6": "grok-4.6",
    "grok-4.6-fast": "grok-4.6-fast",
    "cursor-grok-4.6-xhigh-fast": "grok-4.6-fast",
    "fable": "claude-fable-5-1",
    "fable-5": "claude-fable-5-1",
    "fable-5.1": "claude-fable-5-1",
    "fable-5-1": "claude-fable-5-1",
    "claude-fable-5": "claude-fable-5-1",
    "claude-fable-5-1": "claude-fable-5-1",
    "claude-fable-5.1": "claude-fable-5-1",
    "opus": "claude-opus-5",
    "opus-5": "claude-opus-5",
    "claude-opus-5": "claude-opus-5",
    "claude-opus-5-fast": "claude-opus-5-fast",
    "sol": "gpt-5.6-sol",
    "gpt-5.6": "gpt-5.6-sol",
    "gpt-5.6-sol": "gpt-5.6-sol",
    "gpt-5.6-sol-fast": "gpt-5.6-sol-fast",
    "gpt-5-6-sol": "gpt-5.6-sol",
}


def parse_model(raw: str) -> ModelSelection:
    s = (raw or "grok-4.6-fast").strip()
    if s.startswith("claude-grok"):
        s = s[len("claude-") :]
    s = MODEL_ALIASES.get(s, MODEL_ALIASES.get(s.lower(), s))
    fast = False
    effort = None
    if s.endswith("-fast") or "[fast]" in s:
        fast = True
        s = s.replace("-fast", "").replace("[fast]", "")
    match = re.search(r"\((low|medium|high|xhigh)\)", s)
    if match:
        effort = match.group(1)
        s = (s[: match.start()] + s[match.end() :]).strip()
    s = s.strip() or "grok-4.6"
    cursor_id = MODEL_ALIASES.get(s, s)
    if cursor_id.endswith("-fast"):
        fast = True
        cursor_id = cursor_id[: -len("-fast")]
    cursor_id = {
        "grok-4.6-fast": "grok-4.6",
        "claude-opus-5-fast": "claude-opus-5",
        "gpt-5.6-sol-fast": "gpt-5.6-sol",
    }.get(cursor_id, cursor_id)
    params: list[ModelParameterValue] = []
    if fast and cursor_id in ("grok-4.6", "claude-opus-5", "gpt-5.6-sol", "composer-2.5"):
        params.append(ModelParameterValue(id="fast", value="true"))
    if effort and cursor_id in ("grok-4.6", "claude-opus-5", "claude-fable-5-1"):
        params.append(ModelParameterValue(id="effort", value=effort))
    elif cursor_id == "grok-4.6" and not effort:
        params.append(ModelParameterValue(id="effort", value="xhigh"))
    return ModelSelection(id=cursor_id, params=params)


def is_title_request(tools: list[Any], user_text: str, max_tokens: Any) -> bool:
    if tools:
        return False
    text = (user_text or "").lower()
    if len(text) > 8000:
        return False
    if "title" in text and ("json" in text or "concise" in text or "summar" in text):
        return True
    try:
        return int(max_tokens) <= 32 and "title" in text
    except (TypeError, ValueError):
        return False


def log(msg: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def load_key() -> str:
    env = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if env:
        return env
    if KEY_FILE.is_file():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    raise RuntimeError(f"missing CURSOR_API_KEY and {KEY_FILE}")


def sanitize_tool_name(name: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_]", "_", name or "tool")
    if not out or out[0].isdigit():
        out = "t_" + out
    return out[:64]


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    return "".join(parts)


def extract_system(body: dict[str, Any]) -> str:
    system = body.get("system")
    if isinstance(system, str):
        return system
    return content_to_text(system)


def extract_last_turn(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    tool_results: list[dict[str, Any]] = []
    texts: list[str] = []
    for msg in reversed(messages or []):
        if msg.get("role") != "user":
            if tool_results or texts:
                break
            continue
        content = msg.get("content")
        if isinstance(content, str):
            texts.append(content)
            break
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    tool_results.append(block)
                elif block.get("type") == "text":
                    texts.append(str(block.get("text") or ""))
        if tool_results or texts:
            break
    texts.reverse()
    return tool_results, "\n".join(t for t in texts if t)


class PendingTool:
    def __init__(self, orig_name: str, args: dict[str, Any], call_id: str) -> None:
        self.orig_name = orig_name
        self.args = args
        self.call_id = call_id
        self.event = threading.Event()
        self.result: str = ""
        self.is_error = False


class Session:
    def __init__(self, session_id: str, loop: asyncio.AbstractEventLoop) -> None:
        self.session_id = session_id
        self.loop = loop
        self.agent: AsyncAgent | None = None
        self.tool_map: dict[str, str] = {}  # sanitized -> original
        self.pending: dict[str, PendingTool] = {}
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.lock = threading.Lock()
        self.turn_lock = threading.Lock()
        self.run_in_flight = False
        self.model_key = ""

    def emit(self, event: dict[str, Any]) -> None:
        self.events.put(event)

    def clear_events(self) -> None:
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                break

    def drain_timeout(self, timeout: float) -> dict[str, Any] | None:
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty:
            return None


class Gateway:
    def __init__(self, workspace: str) -> None:
        self.workspace = workspace
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="clc-aio")
        self.client: AsyncClient | None = None
        self.sessions: dict[str, Session] = {}
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.fatal: str | None = None

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self._boot())
        self.loop.run_forever()

    async def _boot(self) -> None:
        try:
            os.environ["CURSOR_API_KEY"] = load_key()
            self.client = await AsyncClient.launch_bridge(
                workspace=self.workspace,
                timeout=60,
            )
            log(f"bridge up workspace={self.workspace}")
            self.ready.set()
        except Exception as exc:
            self.fatal = str(exc)
            log(f"bridge failed: {exc}\n{traceback.format_exc()}")
            self.ready.set()

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(timeout=70):
            raise RuntimeError("Cursor bridge did not become ready in 70s")
        if self.fatal:
            raise RuntimeError(self.fatal)

    def run_coro(self, coro: Any, timeout: float = 600.0) -> Any:
        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return fut.result(timeout=timeout)

    def get_session(self, session_id: str) -> Session:
        with self.lock:
            sess = self.sessions.get(session_id)
            if sess is None:
                sess = Session(session_id, self.loop)
                self.sessions[session_id] = sess
            return sess

    def ensure_agent(self, sess: Session, model: str, tools: list[dict[str, Any]]) -> None:
        wanted = {sanitize_tool_name(t.get("name") or "tool"): t for t in tools if t.get("name")}
        selection = parse_model(model)
        model_key = selection.id + "|" + ",".join(f"{p.id}={p.value}" for p in (selection.params or []))
        if (
            sess.agent is not None
            and sess.tool_map.keys() == wanted.keys()
            and sess.model_key == model_key
        ):
            return
        self.run_coro(self._create_agent(sess, selection, wanted, model_key), timeout=90)

    async def _create_agent(
        self, sess: Session, selection: ModelSelection, wanted: dict[str, dict[str, Any]], model_key: str
    ) -> None:
        if self.client is None:
            raise RuntimeError("bridge client missing")
        key = load_key()
        orig_map: dict[str, str] = {}
        custom: dict[str, CustomTool] = {}
        for san, spec in wanted.items():
            orig = str(spec.get("name") or san)
            orig_map[san] = orig
            schema = spec.get("input_schema") or {"type": "object", "properties": {}}
            custom[san] = CustomTool(
                description=str(spec.get("description") or orig),
                input_schema=schema if isinstance(schema, dict) else {"type": "object"},
                execute=lambda args, ctx, san=san, sess=sess: self._execute(sess, san, args, ctx),
            )
        agent = await AsyncAgent.create(
            AgentOptions(
                model=selection,
                api_key=key,
                tools=["mcp"],
                local=LocalAgentOptions(
                    cwd=self.workspace,
                    setting_sources=[],
                    custom_tools=custom,
                ),
            ),
            client=self.client,
        )
        sess.agent = agent
        sess.tool_map = orig_map
        sess.model_key = model_key
        log(f"session {sess.session_id} model={model_key} tools={list(orig_map)}")

    def _execute(
        self, sess: Session, san: str, args: Any, ctx: CustomToolContext
    ) -> str:
        orig = sess.tool_map.get(san, san)
        call_id = ctx.tool_call_id or f"tool_{uuid.uuid4()}"
        payload = args if isinstance(args, dict) else {"value": args}
        pending = PendingTool(orig, payload, call_id)
        with sess.lock:
            sess.pending[call_id] = pending
        sess.emit({"kind": "tool", "tool": pending})
        if not pending.event.wait(timeout=600):
            pending.is_error = True
            pending.result = "timeout waiting for Claude Code tool_result"
        return pending.result

    async def _send(self, sess: Session, text: str) -> None:
        if sess.agent is None:
            raise RuntimeError("agent missing")
        sess.run_in_flight = True
        log(f"send start session={sess.session_id} chars={len(text)}")

        def on_delta(update: Any) -> None:
            if isinstance(update, TextDeltaUpdate) and update.text:
                sess.emit({"kind": "text", "text": update.text})
            elif isinstance(update, ThinkingDeltaUpdate):
                # Thinking is Cursor-internal. Emitting thinking_delta can hang
                # Claude Code -p when the request did not enable thinking.
                pass
            elif isinstance(update, ToolCallStartedUpdate):
                pass

        try:
            run = await sess.agent.send(text, SendOptions(on_delta=on_delta))
            result = await run.wait()
            status = str(getattr(result, "status", "") or "")
            sess.emit({"kind": "done", "status": status, "text": getattr(result, "result", None)})
            log(f"send done session={sess.session_id} status={status}")
        except Exception as exc:
            sess.emit({"kind": "error", "error": str(exc)})
            log(f"send failed: {exc}\n{traceback.format_exc()}")
        finally:
            sess.run_in_flight = False

    def fulfill_tools(self, sess: Session, tool_results: list[dict[str, Any]]) -> None:
        for block in tool_results:
            tid = str(block.get("tool_use_id") or "")
            content = block.get("content")
            if isinstance(content, list):
                text = content_to_text(content)
            else:
                text = str(content or "")
            with sess.lock:
                pending = sess.pending.pop(tid, None)
            if pending is None:
                # match by order if ids differ
                with sess.lock:
                    if sess.pending:
                        _, pending = sess.pending.popitem()
            if pending is not None:
                pending.is_error = bool(block.get("is_error"))
                pending.result = text
                pending.event.set()


GATEWAY: Gateway | None = None


def sse(handler: BaseHTTPRequestHandler, event: str, data: dict[str, Any]) -> None:
    payload = json.dumps(data, ensure_ascii=False)
    chunk = f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
    handler.wfile.write(chunk)
    handler.wfile.flush()


def handle_messages(handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> None:
    assert GATEWAY is not None
    model = str(body.get("model") or os.environ.get("ANTHROPIC_MODEL") or "grok-4.6-fast")
    stream = bool(body.get("stream"))
    tools = body.get("tools") or []
    if not isinstance(tools, list):
        tools = []
    messages = body.get("messages") or []
    system = extract_system(body)
    session_id = (
        handler.headers.get("x-claude-code-session-id")
        or handler.headers.get("x-session-id")
        or "default"
    )
    sess = GATEWAY.get_session(session_id)
    tool_results, user_text = extract_last_turn(messages)
    log(f"turn session={session_id} model={model} tools={len(tools)} chars={len(user_text)} title={is_title_request(tools, user_text, body.get('max_tokens'))}")

    if is_title_request(tools, user_text, body.get("max_tokens")):
        title = "Cursor session"
        snippet = (user_text or "").strip().splitlines()
        if snippet:
            title = snippet[-1][:60]
        collected = {
            "id": "msg_" + uuid.uuid4().hex[:20],
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [{"type": "text", "text": title}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        if stream:
            handler.send_response(200)
            handler.send_header("Content-Type", "text/event-stream")
            handler.send_header("Cache-Control", "no-cache")
            handler.send_header("Connection", "close")
            handler.end_headers()
            handler.close_connection = True
            sse(handler, "message_start", {"type": "message_start", "message": {**collected, "content": [], "stop_reason": None}})
            sse(handler, "content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
            sse(handler, "content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": title}})
            sse(handler, "content_block_stop", {"type": "content_block_stop", "index": 0})
            sse(handler, "message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 1}})
            sse(handler, "message_stop", {"type": "message_stop"})
            return
        raw = json.dumps(collected).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(raw)))
        handler.end_headers()
        handler.wfile.write(raw)
        return

    with sess.turn_lock:
        sess.clear_events()
        GATEWAY.ensure_agent(sess, model, tools)
        if tool_results:
            GATEWAY.fulfill_tools(sess, tool_results)
        elif user_text:
            deadline = time.time() + 120
            while sess.run_in_flight and time.time() < deadline:
                time.sleep(0.05)
            prompt = user_text
            if system:
                prompt = system.strip() + "\n\n" + user_text
            asyncio.run_coroutine_threadsafe(GATEWAY._send(sess, prompt), GATEWAY.loop)

        msg_id = "msg_" + uuid.uuid4().hex[:20]
        if not stream:
            collected = collect_turn(sess, model, msg_id)
            raw = json.dumps(collected).encode("utf-8")
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(raw)))
            handler.end_headers()
            handler.wfile.write(raw)
            return

        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "close")
        handler.send_header("X-Accel-Buffering", "no")
        handler.end_headers()
        handler.close_connection = True
        sse(
            handler,
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": msg_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": model,
                    "stop_reason": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            },
        )
        stream_turn(handler, sess, model, msg_id)


def collect_turn(sess: Session, model: str, msg_id: str) -> dict[str, Any]:
    text_parts: list[str] = []
    tools: list[PendingTool] = []
    deadline = time.time() + 580
    while time.time() < deadline:
        ev = sess.drain_timeout(0.25)
        if ev is None:
            continue
        kind = ev.get("kind")
        if kind == "text":
            text_parts.append(str(ev.get("text") or ""))
        elif kind == "tool":
            tools.append(ev["tool"])
            t_end = time.time() + 0.15
            while time.time() < t_end:
                extra = sess.drain_timeout(max(0.01, t_end - time.time()))
                if extra and extra.get("kind") == "tool":
                    tools.append(extra["tool"])
                elif extra and extra.get("kind") == "text":
                    text_parts.append(str(extra.get("text") or ""))
            break
        elif kind == "error":
            break
        elif kind == "done":
            leftover = str(ev.get("text") or "")
            if leftover:
                text_parts.append(leftover)
            break
    content: list[dict[str, Any]] = []
    text = "".join(text_parts)
    if text:
        content.append({"type": "text", "text": text})
    for tool in tools:
        content.append(
            {
                "type": "tool_use",
                "id": tool.call_id,
                "name": tool.orig_name,
                "input": tool.args,
            }
        )
    stop = "tool_use" if tools else "end_turn"
    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop,
        "usage": {"input_tokens": 0, "output_tokens": max(1, len(text) // 4)},
    }


def stream_turn(
    handler: BaseHTTPRequestHandler, sess: Session, model: str, msg_id: str
) -> None:
    index = 0
    text_open = False
    thinking_open = False
    output_tokens = 0
    stop = "end_turn"
    deadline = time.time() + 580
    last_ping = time.time()

    def close_text() -> None:
        nonlocal text_open, index
        if text_open:
            sse(handler, "content_block_stop", {"type": "content_block_stop", "index": index})
            text_open = False
            index += 1

    def close_thinking() -> None:
        nonlocal thinking_open, index
        if thinking_open:
            sse(handler, "content_block_stop", {"type": "content_block_stop", "index": index})
            thinking_open = False
            index += 1

    while time.time() < deadline:
        ev = sess.drain_timeout(0.25)
        if ev is None:
            if time.time() - last_ping > 8:
                handler.wfile.write(b": ping\n\n")
                handler.wfile.flush()
                last_ping = time.time()
            continue
        kind = ev.get("kind")
        if kind == "thinking":
            close_text()
            if not thinking_open:
                sse(
                    handler,
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": index,
                        "content_block": {"type": "thinking", "thinking": ""},
                    },
                )
                thinking_open = True
            delta = str(ev.get("text") or "")
            sse(
                handler,
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {"type": "thinking_delta", "thinking": delta},
                },
            )
        elif kind == "text":
            close_thinking()
            if not text_open:
                sse(
                    handler,
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": index,
                        "content_block": {"type": "text", "text": ""},
                    },
                )
                text_open = True
            delta = str(ev.get("text") or "")
            output_tokens += max(1, len(delta) // 4)
            sse(
                handler,
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {"type": "text_delta", "text": delta},
                },
            )
        elif kind == "tool":
            close_thinking()
            close_text()
            tools = [ev["tool"]]
            t_end = time.time() + 0.15
            while time.time() < t_end:
                extra = sess.drain_timeout(max(0.01, t_end - time.time()))
                if extra is None:
                    continue
                if extra.get("kind") == "tool":
                    tools.append(extra["tool"])
                elif extra.get("kind") == "text":
                    # late text before tools
                    if not text_open:
                        sse(
                            handler,
                            "content_block_start",
                            {
                                "type": "content_block_start",
                                "index": index,
                                "content_block": {"type": "text", "text": ""},
                            },
                        )
                        text_open = True
                    sse(
                        handler,
                        "content_block_delta",
                        {
                            "type": "content_block_delta",
                            "index": index,
                            "delta": {"type": "text_delta", "text": extra.get("text") or ""},
                        },
                    )
                    close_text()
            for tool in tools:
                sse(
                    handler,
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": index,
                        "content_block": {
                            "type": "tool_use",
                            "id": tool.call_id,
                            "name": tool.orig_name,
                            "input": tool.args,
                        },
                    },
                )
                sse(handler, "content_block_stop", {"type": "content_block_stop", "index": index})
                index += 1
            stop = "tool_use"
            break
        elif kind == "error":
            close_thinking()
            close_text()
            err = str(ev.get("error") or "cursor error")
            sse(
                handler,
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": index,
                    "content_block": {"type": "text", "text": ""},
                },
            )
            sse(
                handler,
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {"type": "text_delta", "text": err},
                },
            )
            sse(handler, "content_block_stop", {"type": "content_block_stop", "index": index})
            index += 1
            stop = "end_turn"
            break
        elif kind == "done":
            leftover = str(ev.get("text") or "")
            if leftover and not text_open:
                sse(
                    handler,
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": index,
                        "content_block": {"type": "text", "text": ""},
                    },
                )
                text_open = True
                sse(
                    handler,
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": index,
                        "delta": {"type": "text_delta", "text": leftover},
                    },
                )
            close_thinking()
            close_text()
            break

    close_thinking()
    close_text()
    sse(
        handler,
        "message_delta",
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop, "stop_sequence": None},
            "usage": {"output_tokens": max(1, output_tokens)},
        },
    )
    sse(handler, "message_stop", {"type": "message_stop"})


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        log("%s - " % self.address_string() + fmt % args)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _json(self, code: int, obj: Any) -> None:
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_HEAD(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        self.send_response(200 if path in ("/health", "/", "/api/hello") else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/health", "/", "/api/hello"):
            self._json(200, {"ok": True, "service": "clc-cursor-gateway"})
            return
        if path == "/v1/models":
            data = [
                {"id": mid, "type": "model", "display_name": f"Cursor {mid}"}
                for mid in DEFAULT_MODELS
            ]
            self._json(200, {"data": data, "object": "list"})
            return
        self._json(404, {"error": {"type": "not_found", "message": path}})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._read_json()
        except Exception:
            self._json(400, {"error": {"type": "invalid_request_error", "message": "bad json"}})
            return
        if path in ("/v1/messages/count_tokens", "/v1/messages/count_tokens/"):
            blob = json.dumps(body)
            self._json(200, {"input_tokens": max(1, len(blob) // 4)})
            return
        if path in ("/v1/messages", "/v1/messages/"):
            try:
                handle_messages(self, body)
            except Exception as exc:
                log(f"/v1/messages failed: {exc}\n{traceback.format_exc()}")
                if not self.wfile.closed:
                    try:
                        self._json(
                            500,
                            {"error": {"type": "api_error", "message": str(exc)}},
                        )
                    except Exception:
                        pass
            return
        self._json(404, {"error": {"type": "not_found", "message": path}})


def main() -> int:
    parser = argparse.ArgumentParser(description="clc Cursor Anthropic gateway")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--workspace", default=os.environ.get("CLC_WORKSPACE") or os.getcwd())
    args = parser.parse_args()
    global GATEWAY
    GATEWAY = Gateway(workspace=args.workspace)
    log(f"starting bridge workspace={args.workspace}")
    GATEWAY.start()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    log(f"listening http://{args.host}:{args.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("shutdown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
