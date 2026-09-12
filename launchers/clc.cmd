@echo off
REM Windows entry point for clc (Cursor Agent TUI + Cloud Agents API).
REM PowerShell's built-in alias `clc` -> Clear-Content wins over PATH unless
REM the user profile removes it. This .cmd is what the profile function calls,
REM and what you can invoke as `clc.cmd` if the alias is still in the way.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\bin\clc.ps1" %*
