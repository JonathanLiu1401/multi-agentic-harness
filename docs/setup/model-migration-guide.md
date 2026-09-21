# Model Migration Guide for Multi-Agentic Harness (CLX, CLG, CLD, CLO, CLC, Claude)

This guide documents the exact procedure for future agents to migrate or upgrade models across all profiles and harnesses in this ecosystem.

---

## 1. Profiles & Architecture Overview

| Profile | Backend / Protocol | Context Ceiling | Default / Canonical Models | Config Dir | Key Files |
|---|---|---|---|---|---|
| **`clx`** | xAI Grok via CLIProxyAPI (`127.0.0.1:8317`) | 500k | `grok-4.7(high)`, `grok-4.7-fast(high)`, `grok-4.6(high)` | `~/.claude-clx` | `settings.json`, `agents/grok.md`, `CLAUDE.md`, `launchers/clx*` |
| **`clg`** | Google Gemini (Antigravity) via CLIProxyAPI (`127.0.0.1:8317`) | 1M | `gemini-3.8-flash-high(high)` | `~/.claude-clg` | `settings.json`, `agents/agy-gemini-3-8-flash.md`, `CLAUDE.md`, `launchers/clg*` |
| **`cld`** | DeepSeek Anthropic API (`api.deepseek.com/anthropic`) | 1M | `deepseek-flash[1m]` | `~/.claude-cld` | `settings.json`, `agents/deepseek.md`, `CLAUDE.md`, `launchers/cld*` |
| **`clo`** | OpenRouter Anthropic Skin (`openrouter.ai/api`) | 1M | `stealth/union-alpha[1m]` | `~/.claude-clo` | `settings.json`, `agents/openrouter.md`, `CLAUDE.md`, `launchers/clo*` |
| **`clc`** | Cursor CLI via local translator (`127.0.0.1:8318`) | 1M | `grok-4.7-fast` | `~/.claude-clc` | `settings.json`, `CLAUDE.md`, `launchers/clc*` |
| **`claude`** | Anthropic Direct OAuth (`api.anthropic.com`) | 200k / 1M | `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5` | `~/.claude` | `settings.json`, `CLAUDE.md` |
| **Grok CLI** | Native Grok Build TUI / CLI (`~/.grok/bin/grok.exe`) | 500k | `grok-4.7-build-fast`, `grok-4.7` | `~/.grok` | `config.toml`, `models_cache.json` |

---

## 2. Fundamental Rules & Mechanics

1. **Effort Levels in CLIProxyAPI:**
   - In proxy-backed profiles (`clx`, `clg`), reasoning effort is passed as a `(level)` suffix on the model ID, e.g. `grok-4.7(high)` or `gemini-3.8-flash-high(high)`.
   - Valid proxy effort levels: `minimal`, `low`, `medium`, `high`, `xhigh`, `auto`, `none`.
   - `(level)` and `[1m]` cannot be combined in one ID; the proxy will return 400.
   - Claude Code's internal `/effort` command does NOT apply to non-Claude IDs; set `CLAUDE_CODE_EFFORT_LEVEL` in launcher scripts.

2. **Context Windows:**
   - Context limits are process-wide in Claude Code.
   - For 500k models (Grok): `CLAUDE_CODE_MAX_CONTEXT_TOKENS=500000` and `CLAUDE_CODE_AUTO_COMPACT_WINDOW=500000`.
   - For 1M models (Gemini, DeepSeek, OpenRouter): both variables must be set to `1000000`.
   - This is why Grok (`clx`) and Gemini (`clg`) MUST use separate launcher profiles and config directories.

3. **Repo vs Deployed Synchronization:**
   - `install-windows.ps1` and launchers copy files to live locations (`~/.claude-*`, `~/.agent-bridge/`, `~/bin/`).
   - Every model migration MUST update BOTH the repo template and the live deployed directory.

---

## 3. Migration Recipes by Harness

### A. Grok Migration (e.g. Grok 4.7 -> Grok 4.8) in `clx`

1. **Verify Upstream Support:**
   - Test in Grok CLI: `& "$HOME\.grok\bin\grok.exe" models`
   - Check `~/.grok/models_cache.json` for model names and reasoning effort tiers.
   - Check CLIProxyAPI `/v1/models` on `http://127.0.0.1:8317/v1/models`.

2. **Configure CLIProxyAPI Alias (if fast mode or custom alias needed):**
   - Edit `C:\Users\jonny\cliproxyapi\config.yaml` under `oauth-model-alias.xai`:
     ```yaml
     oauth-model-alias:
       xai:
         - name: "grok-4.8"
           alias: "grok-4.8-fast"
           display-name: "Grok 4.8 Fast"
           fork: true
     ```
   - Restart gateway: `& "C:\Users\jonny\cliproxyapi\start-gateway.ps1"`

3. **Update Grok CLI Config:**
   - Edit `~/.grok/config.toml`:
     ```toml
     [models]
     default = "grok-4.8-build-fast"
     default_reasoning_effort = "xhigh"

     [model.grok-4.8]
     context_window = 500000

     [model.grok-4.8-build-fast]
     context_window = 500000
     ```

4. **Update `settings.json` (both Repo & Deployed):**
   - Files:
     - `C:\Users\jonny\.claude-clx\settings.json`
     - `github-tools\multi-agentic-harness\templates\claude-clx\settings.json`
   - Update:
     - `"model": "grok-4.8(high)"`
     - `"availableModels"`: add `grok-4.8(high)`, `grok-4.8(xhigh)`, `grok-4.8(medium)`, `grok-4.8(low)` and fast variants.
     - `"modelPicker.options"`: add labeled rows for the new models.
     - `"modelPricing.overrides"`: add pricing entries ($2/M in, $6/M out for standard; 2x for fast).

5. **Update Subagent Definition:**
   - Files:
     - `C:\Users\jonny\.claude-clx\agents\grok.md`
     - `github-tools\multi-agentic-harness\plugin\agents\grok.md`
   - Change frontmatter: `model: grok-4.8(high)` and update prompt text.

6. **Update Launchers:**
   - Files:
     - `C:\Users\jonny\bin\clx.ps1`
     - `C:\Users\jonny\bin\clx`
     - `github-tools\multi-agentic-harness\launchers\clx.ps1`
     - `github-tools\multi-agentic-harness\launchers\clx`
   - Update:
     - `$env:ANTHROPIC_MODEL = "grok-4.8(high)"`
     - `$env:ANTHROPIC_DEFAULT_MODEL = "grok-4.8(high)"`
     - `$env:ANTHROPIC_CUSTOM_MODEL_OPTION = "grok-4.8(high)"`
     - `$env:CLAUDE_CODE_SUBAGENT_MODEL = "grok-4.8(high)"`

7. **Update Bridge & Runners:**
   - Files:
     - `github-tools\multi-agentic-harness\visible_agent_bridge.py`
     - `github-tools\multi-agentic-harness\grok_worker_runner.py`
     - Copy to `C:\Users\jonny\.agent-bridge\`
   - Set: `GROK_MODEL = "grok-4.8"`, `HARNESS_DEFAULT_MODELS["clx"] = "grok-4.8(high)"`.

8. **Update models.json & Skills:**
   - `github-tools\multi-agentic-harness\models.json` -> `"grok": { "id": "grok-4.8", "window": "" }`
   - `plugin/skills/claude-manages-codex/SKILL.md` and `~/.claude/skills/claude-manages-codex/SKILL.md`.

---

### B. Gemini Migration (e.g. Gemini 3.8 -> 3.9) in `clg`

1. **Verify Model ID:**
   - Inspect `/v1/models` on CLIProxyAPI:
     ```powershell
     python -c "import urllib.request, json; req = urllib.request.Request('http://127.0.0.1:8317/v1/models', headers={'Authorization': 'Bearer ccp-d6dad8aa2b92f036eec74ef9cca8fe662af4316f16dec05e'}); res = urllib.request.urlopen(req); data = json.loads(res.read()); print([m['id'] for m in data.get('data', []) if 'gemini' in m['id']])"
     ```
   - Check if new model requires `-high` or other tier suffix (e.g. `gemini-3.9-flash-high`).

2. **Probe Inference:**
   - Send test POST to `http://127.0.0.1:8317/v1/messages` with model `gemini-3.9-flash-high(high)`.
   - Confirm thinking blocks return with valid signature.

3. **Update `settings.json` (both Repo & Deployed):**
   - Files:
     - `C:\Users\jonny\.claude-clg\settings.json`
     - `github-tools\multi-agentic-harness\templates\claude-clg\settings.json`
   - Update default `"model"`, `"availableModels"`, `"modelPicker"`, and `"modelPricing"`.

4. **Update Subagent Definition:**
   - Files:
     - `C:\Users\jonny\.claude-clg\agents\agy-gemini-3-8-flash.md` (rename or update)
     - `github-tools\multi-agentic-harness\plugin\agents\`

5. **Update Launchers:**
   - Files:
     - `C:\Users\jonny\bin\clg.ps1`, `C:\Users\jonny\bin\clg`
     - `github-tools\multi-agentic-harness\launchers\clg.ps1`, `launchers\clg`

6. **Update Bridge:**
   - `visible_agent_bridge.py`: update `HARNESS_DEFAULT_MODELS["clg"]`.

---

### C. DeepSeek Migration (e.g. DeepSeek V4.1 -> V4.2) in `cld`

1. **Verify Endpoint:**
   - Direct Anthropic endpoint: `https://api.deepseek.com/anthropic/v1/messages`.
   - Verify context window and thinking parameters.

2. **Update Files:**
   - `C:\Users\jonny\.claude-cld\settings.json` and repo template.
   - `C:\Users\jonny\.claude-cld\agents\deepseek.md` and repo template.
   - `C:\Users\jonny\bin\cld.ps1`, `cld`, and repo launchers.
   - `visible_agent_bridge.py`: update `HARNESS_DEFAULT_MODELS["cld"]`.

---

### D. OpenRouter Migration in `clo`

1. **Verify OpenRouter Model Slug:**
   - Check OpenRouter model catalog for exact wire ID (e.g. `stealth/union-alpha[1m]`, `anthropic/claude-3.7-sonnet`).

2. **Update Files:**
   - `C:\Users\jonny\.claude-clo\settings.json` and repo template.
   - `C:\Users\jonny\.claude-clo\agents\openrouter.md` and repo template.
   - `C:\Users\jonny\bin\clo.ps1`, `clo`, and repo launchers.
   - `visible_agent_bridge.py`: update `HARNESS_DEFAULT_MODELS["clo"]`.

---

### E. Cursor Migration in `clc`

1. **Verify Translator & Models:**
   - Check local Cursor Anthropic gateway on port 8318 (`gateway/cursor_anthropic_gateway.py`).
   - Check `cursor-agent models` or Cursor config for available models.

2. **Update Files:**
   - `C:\Users\jonny\.claude-clc\settings.json` and repo template.
   - `C:\Users\jonny\bin\clc.ps1`, `clc`, and repo launchers.
   - `visible_agent_bridge.py`: update `HARNESS_DEFAULT_MODELS["clc"]`.

---

## 4. Verification Checklist

After editing the files, execute this checklist:

- [ ] **Gateway Health:** Run `start-gateway.ps1` to restart CLIProxyAPI cleanly without orphaned port listeners.
- [ ] **Direct HTTP Probe:** POST to `/v1/messages` with the target model and verify HTTP 200, thinking block output, and valid tokens.
- [ ] **Bridge Sync:** Confirm `visible_agent_bridge.py` in `C:\Users\jonny\.agent-bridge\` matches `github-tools\multi-agentic-harness\visible_agent_bridge.py`.
- [ ] **CLI Check:** If Grok was updated, run `& "$HOME\.grok\bin\grok.exe" models` to verify the default model.
- [ ] **Git Sync:** Check `git status` in `github-tools/multi-agentic-harness`, commit with descriptive message, and push to `main`.
