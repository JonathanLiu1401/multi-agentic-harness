@echo off
REM Windows entry point for clo (OpenRouter profile, 1M context).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\bin\clo.ps1" %*
