@echo off
rem Boot launcher: QQ bot stack (SnowLuma + qq-bridge), memory sync, voice services.
rem All hidden via wscript: nothing to close by accident.
rem ASCII only on purpose: cmd.exe mangles UTF-8 batch files.
setlocal
set "H=%~dp0.."
set "LOG=%H%\boot.log"

echo [%date% %time%] boot check >> "%LOG%"

rem ---- snapshot memory + persona card before anything can clobber them ----
powershell -NoProfile -ExecutionPolicy Bypass -File "%H%\backup-bot-state.ps1" -Force >> "%LOG%" 2>&1

rem ---- re-apply the real-@ patch to the bilibili plugin's mcp_server.py ----
rem The plugin re-ships that file on every upgrade, which wipes the patch.
rem The script is idempotent: already patched -> no-op.
"%H%\astrbot\.venv\Scripts\python.exe" "%H%\patch-bili-mention.py" >> "%LOG%" 2>&1

rem ---- voice services: MiniMax TTS (port 8851) + MiMo TTS (8850) + RVC fallback (8848) ----
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'minimax-tts-daemon|mimo-tts-daemon|voice-daemon' }) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting voice services >> "%LOG%"
    wscript.exe //nologo "%H%\start-voice-hidden.vbs"
) else (
    echo [%date% %time%] voice services already running >> "%LOG%"
)

rem ---- QQ client: SnowLuma can only hook a running QQ, and nothing else starts it ----
tasklist /FI "IMAGENAME eq QQ.exe" 2>nul | find /I "QQ.exe" >nul
if errorlevel 1 (
    echo [%date% %time%] starting QQ >> "%LOG%"
    start "" "D:\QQ.exe"
    ping -n 31 127.0.0.1 >nul
) else (
    echo [%date% %time%] QQ already running >> "%LOG%"
)

rem ---- SnowLuma gateway (QQ side, WebUI 5099, OneBot http 3000 / ws 3001) ----
rem runtime.json hookAutoLoad=true makes it inject the logged-in QQ by itself.
netstat -ano | findstr "LISTENING" | findstr ":5099" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting SnowLuma >> "%LOG%"
    wscript.exe //nologo "%H%\start-snowluma-hidden.vbs"
    ping -n 31 127.0.0.1 >nul
) else (
    echo [%date% %time%] SnowLuma already running >> "%LOG%"
)

rem ---- keep qq-bridge pointed at DSH's current web port (DSH picks a random one each launch) ----
powershell -NoProfile -ExecutionPolicy Bypass -File "%H%\sync-dsh-port.ps1" >nul 2>&1

rem ---- qq-bridge (node, talks to DSH + SnowLuma) ----
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { $_.CommandLine -match 'bridge\.js' }) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting qq-bridge >> "%LOG%"
    wscript.exe //nologo "%H%\start-bridge-hidden.vbs"
) else (
    echo [%date% %time%] qq-bridge already running >> "%LOG%"
)

rem ---- shared memory sync loop (QQ memory + bilibili memory -> one file) ----
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | Where-Object { $_.CommandLine -match 'sync-memory-loop' }) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting memory sync >> "%LOG%"
    wscript.exe //nologo "%H%\start-memory-sync-hidden.vbs"
) else (
    echo [%date% %time%] memory sync already running >> "%LOG%"
)

rem ---- fast DSH port follower (checks every 60s, restarts the bridge when DSH moves) ----
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | Where-Object { $_.CommandLine -match 'follow-dsh-port' }) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting port follower >> "%LOG%"
    wscript.exe //nologo "%H%\start-port-follow-hidden.vbs"
) else (
    echo [%date% %time%] port follower already running >> "%LOG%"
)

rem ---- health watchdog: checks the whole stack every 2 min and self-heals ----
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | Where-Object { $_.CommandLine -match 'watchdog-loop' }) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting health watchdog >> "%LOG%"
    wscript.exe //nologo "%H%\start-bot-health-hidden.vbs"
) else (
    echo [%date% %time%] health watchdog already running >> "%LOG%"
)
echo [%date% %time%] done >> "%LOG%"
endlocal
