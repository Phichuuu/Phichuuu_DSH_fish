@echo off
rem Watchdog: every 2 minutes check the QQ bot stack and self-heal.
rem ASCII only on purpose: cmd.exe mangles UTF-8 batch files.
rem
rem Why 2 minutes: DSH picks a new random web port on every launch, and the bot
rem is silent until the bridge is repointed. A short cycle means any DSH restart
rem is noticed (and repaired) almost immediately.
setlocal
set "H=%~dp0.."
set "PS=powershell -NoProfile -ExecutionPolicy Bypass -File"

:loop
%PS% "%H%\check-bot-health.ps1" -Repair -Quiet
ping -n 121 127.0.0.1 >nul
goto loop
