#!/usr/bin/env python3
"""Visible-window runner for Grok Build CLI workers (macOS / Linux / Windows).

Launched by visible_agent_bridge.py as:  python grok_worker_runner.py <run_dir>

Mirrors the Windows PowerShell grok runner's state machine so
get_visible_run_status, steer, captain-help, and watchers work unchanged:

  initial turn -> auto captain report -> steer-queue loop -> git summary -> exit

Grok specifics (probed against grok 1.0.34 on an Intel Mac):
  - Headless turn: ``grok --prompt-file <path> --output-format streaming-json``.
  - Do not combine ``-p``/``--single`` with ``--prompt-file``.
  - Resume is ``-r <sessionId>``.
  - streaming-json is NDJSON with type tags: thought, text, tool_call,
    tool_call_update, usage, end (sessionId), error.
  - Read-only is ``--disallowed-tools Write,Edit`` (Bash kept).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CAPTAIN_REPORTS_DIR = "captain_reports"
FINAL_JSON = "final.json"
FINAL_MD = "final.md"


def _now_iso() -> str:
    return _dt.datetime.now().isoformat()


def _set_console_title(title: str) -> None:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except Exception:
            pass
        return
    try:
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()
    except Exception:
        pass


class Run:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8-sig"))
        self.prompt_path = run_dir / "prompt.md"
        self.events_path = run_dir / "events.jsonl"
        self.display_path = run_dir / "display.log"
        self.status_path = run_dir / "status.json"
        self.session_path = run_dir / "session_id.txt"
        self.steer_queue = run_dir / "steer_queue"
        self.steer_done = run_dir / "steer_done"
        self.reports_dir = run_dir / CAPTAIN_REPORTS_DIR
        self.steer_queue.mkdir(parents=True, exist_ok=True)
        self.steer_done.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.cwd = str(self.metadata.get("cwd") or Path.cwd())
        self.session_id: str = (self.metadata.get("resume_session_id") or "").strip()
        if self.session_id:
            self.session_path.write_text(self.session_id, encoding="utf-8")
        self.error_message = ""

    def _append(self, path: Path, text: str) -> None:
        for _ in range(25):
            try:
                with path.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(text + "\n")
                return
            except OSError:
                time.sleep(0.015)

    def raw(self, line: str) -> None:
        self._append(self.events_path, line)

    def display(self, text: str) -> None:
        self._append(self.display_path, text)

    def emit(self, text: str) -> None:
        self.display(text)
        print(text, flush=True)

    def log(self, text: str) -> None:
        stamp = _dt.datetime.now().strftime("%H:%M:%S")
        self.emit(f"[{stamp}] {text}")

    def set_status(self, status: str) -> None:
        payload = json.dumps(
            {"status": status, "updated_at": _now_iso(), "run_dir": str(self.run_dir)},
            indent=2,
        )
        tmp = self.status_path.with_suffix(".json.tmp")
        for _ in range(5):
            try:
                tmp.write_text(payload, encoding="utf-8")
                os.replace(tmp, self.status_path)
                return
            except OSError:
                time.sleep(0.2)
        self.log(f"Set-Status failed after 5 attempts: {status}")

    def _report_mtime(self) -> float:
        fp = self.reports_dir / FINAL_JSON
        try:
            return fp.stat().st_mtime
        except OSError:
            return 0.0

    def auto_captain_report(self, outcome: str, summary: str, baseline: float) -> None:
        if self._report_mtime() > baseline:
            return
        now = _now_iso()
        record = {
            "report_id": f"{self.run_dir.name}-auto",
            "status": "submitted",
            "outcome": outcome,
            "created_at": now,
            "updated_at": now,
            "run_dir": str(self.run_dir),
            "thread_id": None,
            "session_id": self.session_id or None,
            "summary": summary,
            "changed_files": [],
            "verification": [],
            "risks": [],
            "questions": [],
            "close_tui": True,
            "auto_generated": True,
            "agent": "grok",
        }
        (self.reports_dir / FINAL_JSON).write_text(json.dumps(record, indent=2), encoding="utf-8")
        md = (
            f"# Captain Report\n\nReport ID: {record['report_id']}\nOutcome: {outcome}\n"
            f"Created: {now}\nRun directory: {self.run_dir}\n\n## Summary\n\n{summary}\n"
        )
        (self.reports_dir / FINAL_MD).write_text(md, encoding="utf-8")

    def _grok_bin(self) -> str:
        stored = str(self.metadata.get("grok_cli") or "").strip()
        if stored and Path(stored).exists():
            return stored
        found = shutil.which("grok")
        if found:
            return found
        home = Path.home()
        for candidate in (
            home / ".grok" / "bin" / "grok",
            home / ".grok" / "bin" / "grok.exe",
        ):
            if candidate.exists():
                return str(candidate)
        return stored or "grok"

    def _grok_args(self, prompt_path: Path, resume: str, label: str) -> list[str]:
        md = self.metadata
        args = [
            self._grok_bin(),
            "--prompt-file",
            str(prompt_path),
            "--output-format",
            "streaming-json",
            "--cwd",
            self.cwd,
            "--permission-mode",
            "bypassPermissions",
            "-m",
            str(md.get("model") or "grok-4.7"),
        ]
        effort = md.get("requested_reasoning_effort") or ""
        candidate = str(effort).strip().lower()
        if candidate in ("low", "medium", "high", "xhigh"):
            args += ["--reasoning-effort", candidate]
        requested = str(md.get("requested_sandbox") or "").strip().lower()
        if requested == "read-only":
            args += ["--disallowed-tools", "Write,Edit"]
        extra = md.get("initial_extra_args")
        if label == "initial" and not resume and isinstance(extra, list):
            args += [str(part) for part in extra if str(part).strip()]
        if resume:
            args += ["-r", resume]
        return args

    def _turn_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUNBUFFERED", "1")
        return env

    def _ingest_event(self, obj: dict, chunks: list[str], thought_noted: list[bool]) -> None:
        otype = obj.get("type")
        sid = obj.get("sessionId") or obj.get("session_id")
        if isinstance(sid, str) and sid and sid != self.session_id:
            self.session_id = sid
            self.session_path.write_text(sid, encoding="utf-8")
        if otype == "thought":
            if not thought_noted[0]:
                self.log(
                    "Model is reasoning (hidden reasoning tokens are not shown; "
                    "the coherent answer block follows when the turn ends)."
                )
                thought_noted[0] = True
            return
        if otype == "text":
            data = obj.get("data")
            if data:
                text = str(data)
                chunks.append(text)
                print(text, end="", flush=True)
                self.display(text)
            return
        if otype == "end":
            if sid:
                self.session_id = str(sid)
                self.session_path.write_text(self.session_id, encoding="utf-8")
            self.log(f"Turn ended: stopReason={obj.get('stopReason')} sessionId={sid}")
            return
        if otype == "error":
            self.error_message = str(obj.get("message") or "grok error")
            self.set_status(f"failed:{self.error_message}")
            self.log(f"Error: {self.error_message}")
            return
        if otype == "tool_call":
            name = obj.get("toolName") or obj.get("title") or "tool"
            self.log(f"Tool: {name} ({obj.get('status') or 'in_progress'})")
            return
        if otype in ("tool_call_update", "usage", "plan", "available_commands"):
            return
        self.log(f"Event: {otype}")

    def run_turn(self, prompt_path: Path, resume: str, label: str) -> tuple[int, str]:
        self.set_status(f"running:{label}")
        self.error_message = ""
        self.log(
            f"Starting Grok {'resume ' if resume else ''}turn: {label}"
            + (f" | session: {resume}" if resume else "")
        )
        dropped = self.metadata.get("dropped_extra_args") or []
        if label == "initial" and dropped:
            self.log(
                "[warn] this grok build does not support: "
                + " ".join(str(x) for x in dropped)
                + " - dropped so the run can start"
            )
        args = self._grok_args(prompt_path, resume, label)
        logged = []
        skip_next = False
        for i, a in enumerate(args):
            if skip_next:
                skip_next = False
                continue
            if a == "--prompt-file" and i + 1 < len(args):
                logged.append(a)
                logged.append(args[i + 1])
                skip_next = True
            else:
                logged.append(a)
        self.log("Command: " + " ".join(logged))
        chunks: list[str] = []
        thought_noted = [False]
        try:
            proc = subprocess.Popen(
                args,
                cwd=self.cwd,
                env=self._turn_env(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            self.set_status(f"failed:spawn:{exc}")
            return 1, f"failed to spawn grok CLI: {exc}"
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")
            if not line.strip():
                continue
            self.raw(line)
            try:
                obj = json.loads(line)
            except ValueError:
                self.log(line)
                continue
            if isinstance(obj, dict):
                self._ingest_event(obj, chunks, thought_noted)
        code = proc.wait()
        answer = "".join(chunks).strip()
        if answer:
            self.emit(f"\n===== Grok answer ({label}) =====\n{answer}\n===== end Grok answer =====\n")
        if code == 0 and self.error_message:
            code = 1
            answer = answer or self.error_message
        self.log(f"Grok turn '{label}' exited with code {code}")
        if code != 0 and not answer:
            answer = self.error_message or "(grok turn failed before producing a text answer; see events.jsonl)"
        return code, answer

    def _compose_with_haiku(self) -> Path:
        composer_prompt_path = self.run_dir / "composer_prompt.md"
        composed_path = self.run_dir / "composed_prompt.md"
        prelude_path = self.run_dir / "grok_prelude.md"
        if not composer_prompt_path.exists():
            return self.prompt_path
        claude = str(self.metadata.get("claude_cli") or shutil.which("claude") or "claude")
        composer_model = str(self.metadata.get("prompt_composer_model") or "haiku")
        composer_effort = str(self.metadata.get("prompt_composer_effort") or "low")
        composer_budget = str(self.metadata.get("prompt_composer_max_budget_usd") or "1.00")
        self.log(
            f"Haiku prompt composer enabled. Model: {composer_model} | "
            f"Effort: {composer_effort} | Max budget USD: {composer_budget}"
        )
        args = [
            claude, "-p", "--safe-mode", "--no-session-persistence",
            "--prompt-suggestions", "false", "--verbose",
            "--output-format", "stream-json", "--permission-mode", "plan",
            "--max-budget-usd", composer_budget,
            "--model", composer_model, "--effort", composer_effort,
        ]
        prompt = composer_prompt_path.read_text(encoding="utf-8-sig")
        chunks: list[str] = []
        result_text = ""
        try:
            proc = subprocess.Popen(
                args,
                cwd=self.cwd,
                env=self._turn_env(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            self.log(f"Haiku composer spawn failed ({exc}); falling back to the raw captain brief.")
            return self.prompt_path
        assert proc.stdin is not None and proc.stdout is not None
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except OSError:
            pass
        composer_log = self.run_dir / "composer_events.jsonl"
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not line:
                continue
            self._append(composer_log, line)
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            if obj.get("type") == "assistant" and isinstance(obj.get("message"), dict):
                for c in obj["message"].get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "text" and c.get("text"):
                        chunks.append(str(c["text"]))
            elif obj.get("type") == "result" and obj.get("result"):
                result_text = str(obj["result"])
        code = proc.wait()
        if code != 0:
            self.log(f"Haiku prompt composer exited with code {code}; falling back to the raw captain brief.")
            result_text = ""
        if not result_text.strip():
            result_text = "\n".join(chunks)
        if not result_text.strip():
            self.log("Haiku prompt composer produced an empty Grok prompt; falling back to the raw captain brief.")
            result_text = self.prompt_path.read_text(encoding="utf-8-sig")
            heading = "\n\n## Captain Brief (raw; Haiku composer unavailable)\n\n"
        else:
            heading = "\n\n## Haiku-Composed Worker Brief\n\n"
        prelude = prelude_path.read_text(encoding="utf-8-sig") if prelude_path.exists() else ""
        final_prompt = prelude.rstrip() + heading + result_text.strip()
        composed_path.write_text(final_prompt, encoding="utf-8")
        self.log("Composed Grok prompt follows:")
        self.emit(final_prompt)
        return composed_path

    def next_steer_file(self) -> Path | None:
        try:
            files = sorted(p for p in self.steer_queue.glob("*.md") if p.is_file())
        except OSError:
            return None
        return files[0] if files else None

    def main(self) -> int:
        md = self.metadata
        steer_idle = max(0, min(int(md.get("steer_idle_seconds") or 20), 300))
        _set_console_title(f"Grok visible worker - {self.run_dir.name}")
        self.set_status("running")
        self.log(f"Run directory: {self.run_dir}")
        self.log(f"CWD: {self.cwd}")
        self.log(
            f"Model: {md.get('model')} | Requested sandbox: {md.get('requested_sandbox')} | "
            f"Effort: {md.get('effective_reasoning_effort') or md.get('requested_reasoning_effort') or 'xhigh'}"
        )
        if self.session_id:
            self.log(f"Resuming Grok session: {self.session_id}")

        if md.get("compose_with_haiku"):
            prompt_path = self._compose_with_haiku()
        else:
            prompt_path = self.prompt_path
            self.log("Prompt follows:")
            self.emit(prompt_path.read_text(encoding="utf-8-sig"))

        baseline = self._report_mtime()
        code, answer = self.run_turn(prompt_path, self.session_id, "initial")
        if code == 0:
            self.auto_captain_report("completed", answer or "(no text answer; see events.jsonl)", baseline)
        else:
            self.auto_captain_report("failed", answer, baseline)

        while code == 0:
            waited = 0
            steer = self.next_steer_file()
            while steer is None and waited < steer_idle:
                if waited == 0:
                    self.set_status("waiting_for_steer")
                    self.log(f"Waiting up to {steer_idle}s for queued Claude steering before closing.")
                time.sleep(1)
                waited += 1
                steer = self.next_steer_file()
            if steer is None:
                break
            if not self.session_id:
                self.set_status("failed:steer-no-session")
                self.log(f"Cannot steer without a recorded session id: {steer}")
                code = 1
                break
            self.log(f"Applying queued Claude steering: {steer.name}")
            self.emit(steer.read_text(encoding="utf-8-sig"))
            baseline = self._report_mtime()
            code, answer = self.run_turn(steer, self.session_id, f"steer:{steer.stem}")
            if code == 0:
                self.auto_captain_report("completed", answer or "(no text answer; see events.jsonl)", baseline)
            else:
                self.auto_captain_report("failed", answer, baseline)
            try:
                steer.replace(self.steer_done / steer.name)
            except OSError:
                pass

        self.set_status("completed" if code == 0 else f"failed:{code}")
        try:
            for git_args, label in ((["status", "--short"], "Git status:"), (["diff", "--stat"], "Git diff stat:")):
                out = subprocess.run(
                    ["git", "-C", self.cwd, *git_args],
                    capture_output=True, text=True, timeout=15,
                )
                self.log(label)
                if out.stdout.strip():
                    self.emit(out.stdout.rstrip())
        except Exception as exc:
            self.log(f"Git summary unavailable: {exc}")
        self.log(
            "Grok agent for this run has finished. This window will close in 5 seconds; "
            "logs remain in the run directory."
        )
        time.sleep(5)
        return code


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: grok_worker_runner.py <run_dir>", file=sys.stderr)
        return 2
    run_dir = Path(sys.argv[1]).expanduser().resolve()
    if not (run_dir / "metadata.json").exists():
        print(f"no metadata.json in {run_dir}", file=sys.stderr)
        return 2
    run = Run(run_dir)
    try:
        return run.main()
    except Exception as exc:
        run.set_status(f"failed:runner:{exc}")
        run.log(f"Runner crashed: {exc!r}")
        time.sleep(5)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
