@echo off
rem Fast DSH port follower: DSH picks a random web port on every launch, and the
rem bridge stores a fixed dsh.baseUrl. 20 minutes was too slow after a restart,
rem so this loop checks once a minute instead. ASCII only.
setlocal
set "PS=%~dp0..\sync-dsh-port.ps1"
set "LOGDIR=%USERPROFILE%\.dsh\memory"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

:loop
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS%" -RestartIfChanged >> "%LOGDIR%\dsh-port-loop.log" 2>&1
ping -n 61 127.0.0.1 >nul
goto loop
