@echo off
rem Shared memory sync: merge QQ-side and bilibili-side memory, inject into persona card.
rem Runs every ~20 minutes. ASCII only on purpose: cmd.exe mangles UTF-8 batch files.
setlocal
set "PY=%~dp0..\astrbot\.venv\Scripts\python.exe"
set "SCRIPT=%~dp0..\sync-shared-memory.py"
set "LOGDIR=%USERPROFILE%\.dsh\memory"
set "LOG=%LOGDIR%\sync.log"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

:loop
echo [%date% %time%] >> "%LOG%"
rem DSH may have been restarted on a new web port; follow it and restart the bridge if needed.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\sync-dsh-port.ps1" -RestartIfChanged >> "%LOG%" 2>&1
"%PY%" "%SCRIPT%" >> "%LOG%" 2>&1
rem Snapshot memory + persona card. Silent when nothing changed; keeps 120 revisions.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\backup-bot-state.ps1" >> "%LOG%" 2>&1
ping -n 1201 127.0.0.1 >nul
goto loop
