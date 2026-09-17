#!/usr/bin/env python3
"""Visible-window runner for Google Antigravity (agy) workers.

Launched by visible_agent_bridge.py as:  python agy_worker_runner.py <run_dir>

agy has no streaming JSON and no session id. Each turn is one blocking
``agy -p ...`` call; resume uses ``--continue`` (cwd-scoped, most-recent).
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
        self.output_path = run_dir / "output.txt"
        self.status_path = run_dir / "status.json"
        self.steer_queue = run_dir / "steer_queue"
        self.steer_done = run_dir / "steer_done"
        self.reports_dir = run_dir / CAPTAIN_REPORTS_DIR
        self.steer_queue.mkdir(parents=True, exist_ok=True)
        self.steer_done.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.cwd = str(self.metadata.get("cwd") or Path.cwd())

    def _append(self, path: Path, text: str) -> None:
        for _ in range(25):
            try:
                with path.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(text)
                    if not text.endswith("\n"):
                        fh.write("\n")
                return
            except OSError:
                time.sleep(0.015)

    def display(self, text: str) -> None:
        self._append(self.display_path, text if text.endswith("\n") else text + "\n")

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
        model = self.metadata.get("model")
        record = {
            "report_id": f"{self.run_dir.name}-auto",
            "status": "submitted",
            "outcome": outcome,
            "created_at": now,
            "updated_at": now,
            "run_dir": str(self.run_dir),
            "thread_id": None,
            "session_id": None,
            "summary": summary,
            "changed_files": [],
            "verification": [],
            "risks": [],
            "questions": [],
            "close_tui": True,
            "auto_generated": True,
            "agent": "agy",
            "model": model,
        }
        (self.reports_dir / FINAL_JSON).write_text(json.dumps(record, indent=2), encoding="utf-8")
        md = (
            f"# Captain Report\n\nReport ID: {record['report_id']}\nOutcome: {outcome}\n"
            f"Model: {model}\nCreated: {now}\nRun directory: {self.run_dir}\n\n"
            f"## Summary (full agy stdout for this turn)\n\n{summary}\n"
        )
        (self.reports_dir / FINAL_MD).write_text(md, encoding="utf-8")

    def _agy_bin(self) -> str:
        stored = str(self.metadata.get("agy_cli") or "").strip()
        if stored and Path(stored).exists():
            return stored
        found = shutil.which("agy")
        if found:
            return found
        return stored or "agy"

    def run_turn(self, prompt_text: str, resume_continue: bool, label: str) -> tuple[int, str]:
        self.set_status(f"running:{label}")
        if resume_continue:
            self.log(f"Starting Antigravity resume turn (--continue, cwd-scoped): {label}")
        else:
            self.log(f"Starting Antigravity new turn: {label}")
        self.log("agy has no streaming JSON; stdout is captured when the process exits.")
        model = str(self.metadata.get("model") or "Gemini 3.7 Flash (High)")
        args = [
            self._agy_bin(),
            "-p", prompt_text,
            "--model", model,
            "--dangerously-skip-permissions",
            "--add-dir", self.cwd,
        ]
        if resume_continue:
            args = [
                self._agy_bin(),
                "-p", prompt_text,
                "--continue",
                "--model", model,
                "--dangerously-skip-permissions",
                "--add-dir", self.cwd,
            ]
        stdout_tmp = self.run_dir / "turn_stdout.tmp"
        stderr_tmp = self.run_dir / "turn_stderr.tmp"
        try:
            with stdout_tmp.open("w", encoding="utf-8") as out, stderr_tmp.open("w", encoding="utf-8") as err:
                proc = subprocess.run(
                    args,
                    cwd=self.cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    text=True,
                )
            code = proc.returncode
        except OSError as exc:
            self.set_status(f"failed:spawn:{exc}")
            return 1, f"failed to spawn agy CLI: {exc}"
        answer = ""
        if stdout_tmp.exists():
            answer = stdout_tmp.read_text(encoding="utf-8", errors="replace")
        if answer:
            self._append(self.output_path, answer)
            self.emit(answer.rstrip())
        err_text = ""
        if stderr_tmp.exists():
            err_text = stderr_tmp.read_text(encoding="utf-8", errors="replace")
        if err_text.strip():
            self.log("stderr (display.log only; not appended to output.txt/captain report):")
            self.emit(err_text.rstrip())
        for tmp in (stdout_tmp, stderr_tmp):
            try:
                tmp.unlink()
            except OSError:
                pass
        self.log(f"Antigravity turn '{label}' exited with code {code}")
        return code, answer.strip()

    def next_steer_file(self) -> Path | None:
        try:
            files = sorted(p for p in self.steer_queue.glob("*.md") if p.is_file())
        except OSError:
            return None
        return files[0] if files else None

    def main(self) -> int:
        md = self.metadata
        steer_idle = max(0, min(int(md.get("steer_idle_seconds") or 20), 300))
        _set_console_title(f"Antigravity visible worker - {self.run_dir.name}")
        self.set_status("running")
        self.log(f"Run directory: {self.run_dir}")
        self.log(f"CWD: {self.cwd}")
        self.log(f"Model: {md.get('model')} (effort is baked into the model name)")
        self.log("agy never emits a session id. Steering/resume uses --continue.")
        prompt_text = self.prompt_path.read_text(encoding="utf-8-sig")
        self.log("Prompt follows:")
        self.emit(prompt_text)
        resume = bool(md.get("resume_continue"))
        baseline = self._report_mtime()
        code, answer = self.run_turn(prompt_text, resume, "initial")
        if code == 0:
            self.auto_captain_report("completed", answer or "(empty agy stdout)", baseline)
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
            self.log(f"Applying queued Claude steering: {steer.name}")
            steer_text = steer.read_text(encoding="utf-8-sig")
            self.emit(steer_text)
            baseline = self._report_mtime()
            code, answer = self.run_turn(steer_text, True, f"steer:{steer.stem}")
            if code == 0:
                self.auto_captain_report("completed", answer or "(empty agy stdout)", baseline)
            else:
                self.auto_captain_report("failed", answer, baseline)
            try:
                steer.replace(self.steer_done / steer.name)
            except OSError:
                pass

        self.set_status("completed" if code == 0 else f"failed:{code}")
        self.log(
            "Antigravity agent for this run has finished. This window will close in 5 seconds; "
            "logs remain in the run directory."
        )
        time.sleep(5)
        return code


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: agy_worker_runner.py <run_dir>", file=sys.stderr)
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
