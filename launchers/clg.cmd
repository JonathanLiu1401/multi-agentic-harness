@echo off
REM Windows entry point for clg (Antigravity/Gemini profile, 1M context).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\bin\clg.ps1" %*
