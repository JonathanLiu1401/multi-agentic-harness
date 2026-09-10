# Profile Templates

This directory contains configuration templates for the `clx` (Grok) and `clg` (Gemini) Claude Code profiles.

## Setup Instructions

1. Copy the profile directory to your user home:
   - For clx: `templates/claude-clx` -> `~/.claude-clx/`
   - For clg: `templates/claude-clg` -> `~/.claude-clg/`
2. Link the shared agents and skills:
   - On Windows PowerShell:
     ```powershell
     New-Item -ItemType Junction -Path "$HOME\.claude-clx\agents" -Target "$HOME\.claude\agents"
     New-Item -ItemType Junction -Path "$HOME\.claude-clx\skills" -Target "$HOME\.claude\skills"
     New-Item -ItemType Junction -Path "$HOME\.claude-clg\agents" -Target "$HOME\.claude\agents"
     New-Item -ItemType Junction -Path "$HOME\.claude-clg\skills" -Target "$HOME\.claude\skills"
     ```
   - On Linux / macOS:
     ```bash
     ln -s "$HOME/.claude/agents" "$HOME/.claude-clx/agents"
     ln -s "$HOME/.claude/skills" "$HOME/.claude-clx/skills"
     ln -s "$HOME/.claude/agents" "$HOME/.claude-clg/agents"
     ln -s "$HOME/.claude/skills" "$HOME/.claude-clg/skills"
     ```

## Key Configuration Details

### `settings.json`
- `model`: Sets the default model for the profile.
- `availableModels`: Whitelist of valid model IDs supported through the gateway.
- `enforceAvailableModels`: Set to `true` so invalid/incompatible default models are filtered out.
- `modelPicker`: Customizes the `/model` selector inside Claude Code. Note that this must be an object with an `options` array, not a top-level array.
- `effortLevel`: Set to `high` by default.
- `skipDangerousModePermissionPrompt`: Set to `true` to avoid permission confirmation prompts that stall agent queues during automated runs.

### `CLAUDE.md`
- Profile-specific instructions establishing identity (Grok for clx, Gemini for clg).
- Subagent locality rules: specifies which Agent subagents to spawn natively vs via visible CLI terminals.
