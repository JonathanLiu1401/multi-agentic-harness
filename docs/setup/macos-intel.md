# macOS (Intel) setup

This harness was originally a Windows PowerShell visible-window bridge. On an
Intel Mac (`x86_64`, Homebrew at `/usr/local`) the current tree:

- Resolves `grok`, `claude`, `agy`, and `cursor-agent` from PATH / `~/.grok/bin`
  instead of `C:\Users\jonny\...`
- Opens **Terminal.app** for visible workers (override with `BRIDGE_TERMINAL`,
  skip the window with `BRIDGE_HEADLESS=1`)
- Runs Grok/Agy/Cursor/Claude workers through stdlib Python runners, not
  `powershell.exe`
- Uses Homebrew `cliproxyapi` (`brew services`) on `127.0.0.1:8317`
- Refuses the leftover python.org **3.7** that many Intel Macs prepend via
  `~/.bash_profile`

## Replace a previous install

An older copy (July 2026 on this machine) deployed `~/.agent-bridge` plus a
23-line `~/.local/bin/clx` that shadows `~/bin`. Uninstall that first:

```bash
cd ~/github-tools/multi-agentic-harness
./uninstall-macos.sh
./install-macos.sh
```

`install-macos.sh` runs the uninstaller automatically when it sees the old
files. It does **not** remove:

- Homebrew `cliproxyapi` or `~/.cli-proxy-api` OAuth tokens
- `grok` / `claude` / `cursor-agent` CLIs
- Profile directories such as `~/.claude-clx` (settings are replaced; chats stay)

## Verify

```bash
python3.12 -c "import sys; sys.path.insert(0,'$HOME/.agent-bridge'); import visible_agent_bridge as b; print(b.check_worker_backends())"
```

Grok should report `available: true` with `grok_cli` pointing at
`~/.grok/bin/grok` (Mach-O x86_64). Visible Grok workers then open a Terminal
window running `grok_worker_runner.py`.
