@echo off
REM Windows entry point for cld (DeepSeek profile, 64k context).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\bin\cld.ps1" %*
