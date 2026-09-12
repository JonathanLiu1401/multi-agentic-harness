# Local gateways (CLIProxyAPI + Cursor translator)

This directory provides scripts and templates for:

- CLIProxyAPI (v7.2.147+) on `http://127.0.0.1:8317` for `clx` (Grok) and `clg` (Gemini)
- `cursor_anthropic_gateway.py` on `http://127.0.0.1:8318` for `clc` (Cursor)

`cld` does not use either of these; it talks to DeepSeek directly.

## Architecture

- CLIProxyAPI runs locally, listening on `127.0.0.1:8317`.
- Bound to loopback only (`host: "127.0.0.1"`), preventing unauthorized access from other network interfaces.
- Uses a local client API key configured in `config.yaml` and sent by `clx`/`clg` as `ANTHROPIC_AUTH_TOKEN`.
- Providers are authenticated via OAuth (`--xai-login` for Grok, `--antigravity-login` for Gemini/Antigravity). Tokens are saved in `~/.cli-proxy-api/`.

## Scripts

### 1. `start-gateway.ps1`
Starts the gateway detached:
- Clears any orphaned `cli-proxy-api` processes holding port 8317 first.
- Starts `cli-proxy-api.exe` with `-WindowStyle Hidden` and `-PassThru`, detaching it from the calling console so closing the terminal or pressing Ctrl+C does not kill the gateway (avoiding Windows `STATUS_CONTROL_C_EXIT` / `0xC000013A`).
- Waits up to 20 seconds and checks `Get-NetTCPConnection` to verify port 8317 is actively listening before returning.
- Logs events to `~/.cc-bridge/gateway.log` (encoded as UTF-8) with automatic 10 MB rotation.

### 2. `stop-gateway.ps1`
Stops both the scheduled task (if running) and kills all running `cli-proxy-api` processes:
- Using `Stop-ScheduledTask` alone is insufficient because it terminates only the task's PowerShell wrapper while leaving the gateway executable running, which blocks port 8317.
- This script verifies that port 8317 is free before completing.

### 3. `install-autostart.ps1`
Installs a per-user scheduled task named `CLIProxyAPI`:
- Starts at user logon (`-AtLogOn`).
- Runs with normal user privileges (no Administrator elevation required).
- Safe to re-run: removes any previous registration, cleans up running processes, creates the task, starts it, and verifies connectivity.

To inspect or remove the task:
```powershell
Get-ScheduledTask -TaskName CLIProxyAPI
Unregister-ScheduledTask -TaskName CLIProxyAPI -Confirm:$false
```

### 4. `config.example.yaml`
Template configuration for CLIProxyAPI. Copy to `~/cliproxyapi/config.yaml` and replace the placeholder API key with your own generated local client key. Store the corresponding key in `~/.cc-bridge/secrets/clx-api.key` (mode 600).

## Cursor translator (`clc`)

Cursor has no public Anthropic `/v1/messages`. `cursor_anthropic_gateway.py`
implements that contract and drives `cursor-sdk` (`AsyncClient.launch_bridge`,
`tools=["mcp"]`, Claude Code tools as `custom_tools`). Hidden logon task
`CLCCursorGateway`, same shape as `CLIProxyAPI`.

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\github-tools\multi-agentic-harness\gateway\install-clc-autostart.ps1"
Start-ScheduledTask -TaskName CLCCursorGateway
```

- Translator: `cursor_anthropic_gateway.py` (deployed to `~/.agent-bridge/`)
- Start wrapper: `start-clc-gateway.ps1`
- Task installer: `install-clc-autostart.ps1`
- Key: `~/.cc-bridge/secrets/cursor-api.key`
- Logs: `~/.cc-bridge/clc-gateway.log`

Do not send CLI bracket model ids. Do not set `CLAUDE_CODE_EFFORT_LEVEL` in
`clc.ps1`. Full operator notes: [`docs/setup/clc-cursor-gateway.md`](../docs/setup/clc-cursor-gateway.md).
