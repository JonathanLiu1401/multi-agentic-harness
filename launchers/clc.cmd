@echo off
REM Windows entry point for clc (Cursor models in the Claude Code TUI via :8318).
REM PowerShell's built-in alias `clc` -> Clear-Content wins over PATH unless
REM the user profile removes it. This .cmd is what the profile function calls,
REM and what you can invoke as `clc.cmd` if the alias is still in the way.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\bin\clc.ps1" %*
