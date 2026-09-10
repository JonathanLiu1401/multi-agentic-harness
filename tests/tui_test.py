"""Drive `clx` as a REAL interactive TUI in a pseudo-terminal and read the screen.

Why this exists: `claude -p` print mode does not exercise the TUI, the /model
picker, the status line, or the settings-warning path - every bug found in this
setup was invisible to -p and obvious on first interactive use. Antigravity also
rejects -p specifically (upstream fingerprint filter), so -p actively lies about
which Gemini models work.

Usage:
    python tui_test.py screen                  # launch, screenshot the UI
    python tui_test.py picker                  # open /model, dump the picker
    python tui_test.py ask "what model are you"

Requires pywinpty + pyte (both installed).
"""
import os
import queue
import sys
import threading
import time

# The TUI emits box-drawing glyphs; never let printing them kill the test.
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pyte
import winpty

CR = chr(13)
NL = chr(10)
COLS, ROWS = 200, 50


class Tui:
    def __init__(self, cmd=None, cwd=None):
        # clx is a POSIX sh script; on Windows spawn the .cmd shim.
        cmd = cmd or os.path.join(os.environ["USERPROFILE"], ".local", "bin",
                                  os.environ.get("CLX_CMD", "clx") + ".cmd")
        self.screen = pyte.Screen(COLS, ROWS)
        self.stream = pyte.Stream(self.screen)
        self.pty = winpty.PtyProcess.spawn(
            cmd, dimensions=(ROWS, COLS), cwd=cwd or str(__import__("pathlib").Path.home())
        )
        self.q = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        """pty.read() BLOCKS with no data, which hangs any deadline loop.
        Drain it on a daemon thread into a queue instead."""
        while True:
            try:
                data = self.pty.read(8192)
            except Exception:
                break
            if data:
                self.q.put(data)
            else:
                time.sleep(0.02)

    def pump(self, seconds=2.0):
        """Feed whatever the reader thread collected into the emulator."""
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                self.stream.feed(self.q.get(timeout=0.2))
            except queue.Empty:
                pass

    def render(self, label=""):
        lines = [ln.rstrip() for ln in self.screen.display]
        while lines and not lines[-1]:
            lines.pop()
        if label:
            print("=" * 30, label, "=" * 30)
        print("\n".join(lines))
        return "\n".join(lines)

    def send(self, text):
        self.pty.write(text)

    def close(self):
        try:
            self.pty.write("\x03")
            time.sleep(0.3)
            self.pty.terminate(force=True)
        except Exception:
            pass


def wait_for_ready(t, timeout=60):
    """Wait until the TUI has drawn its prompt."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        t.pump(2.0)
        scr = "\n".join(t.screen.display)
        if "for shortcuts" in scr or "Welcome" in scr or ">" in scr:
            return True
    return False


def cmd_screen():
    t = Tui()
    try:
        wait_for_ready(t)
        t.pump(3.0)
        out = t.render("clx startup screen")
        print()
        for flag, msg in (
            ("Settings Warning", "SETTINGS WARNING PRESENT"),
            ("was ignored", "a settings field was ignored"),
            ("claude-grok", "BAD claude- PREFIX on a grok id"),
            ("claude-gemini", "BAD claude- PREFIX on a gemini id"),
        ):
            if flag in out:
                print("PROBLEM:", msg)
        print("banner model line:", [l for l in out.splitlines() if "rok" in l or "emini" in l][:3])
    finally:
        t.close()


def cmd_picker():
    t = Tui()
    try:
        wait_for_ready(t)
        t.pump(2.0)
        t.send("/model\r")
        t.pump(4.0)
        out = t.render("/model picker")
        rows = [l for l in out.splitlines() if l.strip()]
        print()
        print("rows mentioning a model:",
              len([l for l in rows if "rok" in l or "emini" in l]))
        if "Settings Warning" in out or "was ignored" in out:
            print("PROBLEM: settings warning while opening the picker")
        t.send("\x1b")
        t.pump(1.0)
    finally:
        t.close()


def cmd_select_and_ask(row, prompt):
    """Open /model, choose row N, confirm for this session, then ask."""
    t = Tui()
    try:
        wait_for_ready(t)
        t.pump(2.0)
        t.send("/model" + CR)
        t.pump(4.0)
        t.send(str(row))
        t.pump(1.5)
        t.send("s")          # use for this session only
        t.pump(3.0)
        t.render("after selecting row %s" % row)
        t.send(prompt + CR)
        last = ""
        for _ in range(45):
            t.pump(3.0)
            cur = NL.join(t.screen.display)
            if cur == last and ("rok" in cur or "emini" in cur or "Error" in cur):
                break
            last = cur
        out = t.render("answer")
        if "API Error" in out or "RESOURCE_EXHAUSTED" in out:
            print(NL + "PROBLEM: error on screen")
    finally:
        t.close()


def cmd_ctx():
    """Run /context and report the window the TUI actually believes in."""
    t = Tui()
    try:
        wait_for_ready(t)
        t.pump(2.0)
        t.send("/context" + CR)
        t.pump(6.0)
        out = t.render("/context")
        import re
        for m in re.findall(r"[\d.]+k?/[\d.]+k tokens", out):
            print("  window:", m)
        for line in out.splitlines():
            if "Auto-compact window" in line:
                print(" ", line.strip())
    finally:
        t.close()


def cmd_ask(prompt):
    t = Tui()
    try:
        wait_for_ready(t)
        t.pump(2.0)
        t.send(prompt + "\r")
        # Model replies take a while; pump until the text settles. Permission
        # prompts block forever in manual mode, so approve them as they appear.
        last = ""
        approvals = 0
        for _ in range(40):
            t.pump(3.0)
            cur = "\n".join(t.screen.display)
            if ("Do you want" in cur or "❯ 1. Yes" in cur) and approvals < 6:
                t.send("1\r")
                approvals += 1
                t.pump(2.0)
                last = ""
                continue
            if cur == last and ("rok" in cur or "emini" in cur or "Error" in cur):
                break
            last = cur
        out = t.render("interactive answer")
        print("\npermission prompts approved:", approvals)
        if "API Error" in out or "Error" in out:
            print("\nPROBLEM: an error is on screen")
    finally:
        t.close()


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "screen"
    if what == "screen":
        cmd_screen()
    elif what == "ctx":
        cmd_ctx()
    elif what == "picker":
        cmd_picker()
    elif what == "ask":
        cmd_ask(sys.argv[2])
    elif what == "select":
        cmd_select_and_ask(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
