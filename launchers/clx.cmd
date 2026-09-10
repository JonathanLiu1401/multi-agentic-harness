@echo off
REM Windows entry point for clx: launches Claude Code against the local
REM CLIProxyAPI gateway. Lives in ~/.local/bin because that IS on the Windows
REM PATH (~/bin is Git Bash only), and uses .cmd because .PS1 is not in PATHEXT.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\bin\clx.ps1" %*
