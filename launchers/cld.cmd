@echo off
REM cld = direct-Anthropic escape hatch (pure claude.ai path, Remote Control works).
REM Uses the ~/.claude-direct config dir AND force-pins ANTHROPIC_BASE_URL to
REM api.anthropic.com via --settings. The pin is REQUIRED: when cwd is under
REM C:\Users\jonny, the CLI also loads ~/.claude/settings.json as PROJECT-scope
REM settings, whose env block points at the local proxy (127.0.0.1:8317) —
REM without the pin, cld sessions silently route through the proxy and Remote
REM Control breaks. --settings has the highest precedence and wins over that.
REM Refreshes the OAuth credential copy from ~/.claude on each launch.
copy /Y "%USERPROFILE%\.claude\.credentials.json" "%USERPROFILE%\.claude-direct\.credentials.json" >nul 2>&1

REM --- one-time self-healing: junction projects -> shared session store ---
REM All three worlds share ~/.claude/projects so /resume shows every chat.
REM The swap can only happen while no cld session holds the folder, so each
REM launch tries once: if projects is a real dir (not yet a junction), rename
REM it away, top-up-sync into the shared store, and junction it. Silent no-op
REM once done or while still locked.
fsutil reparsepoint query "%USERPROFILE%\.claude-direct\projects" >nul 2>&1
if errorlevel 1 (
  ren "%USERPROFILE%\.claude-direct\projects" projects.premerge.bak >nul 2>&1
  if not errorlevel 1 (
    robocopy "%USERPROFILE%\.claude-direct\projects.premerge.bak" "%USERPROFILE%\.claude\projects" /E /XC /XN /XO /NFL /NDL /NJH /NP >nul 2>&1
    mklink /J "%USERPROFILE%\.claude-direct\projects" "%USERPROFILE%\.claude\projects" >nul 2>&1
  )
)

set "ANTHROPIC_BASE_URL="
set "ANTHROPIC_AUTH_TOKEN="
set "ANTHROPIC_API_KEY="
set "CLAUDE_CONFIG_DIR=%USERPROFILE%\.claude-direct"
claude --settings "%USERPROFILE%\.claude-direct\force-direct.json" %*
