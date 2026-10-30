@echo off
rem ===================================================================
rem  start-bots.cmd -- 一条命令拉起整条链
rem
rem  顺序：备份 -> 语音服务 -> QQ -> SnowLuma -> 端口跟随 -> 桥接
rem        -> 记忆同步 -> 健康看门狗
rem
rem  幂等：已经在跑的不会重复启动。
rem  ASCII only：cmd.exe 按本地代码页读批处理，中文会乱码。
rem ===================================================================
setlocal
call "%~dp0paths.cmd"
set "H=%~dp0"
set "ROOT=%~dp0.."
set "LOG=%ROOT%\boot.log"

echo [%date% %time%] boot check >> "%LOG%"

rem ---- 先备份：记忆和人格卡最容易被误操作清掉 ----
powershell -NoProfile -ExecutionPolicy Bypass -File "%H%backup-bot-state.ps1" -Force >> "%LOG%" 2>&1

rem ---- 语音服务：MiniMax(8851) / MiMo(8850) / 本地 RVC(8848) ----
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'minimax-tts-daemon|mimo-tts-daemon|voice-daemon' }) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting voice services >> "%LOG%"
    wscript.exe //nologo "%H%start-voice-hidden.vbs"
) else (
    echo [%date% %time%] voice services already running >> "%LOG%"
)

rem ---- QQ 客户端：SnowLuma 只能 hook 一个已经在跑的 QQ ----
tasklist /FI "IMAGENAME eq QQ.exe" 2>nul | find /I "QQ.exe" >nul
if errorlevel 1 (
    echo [%date% %time%] starting QQ >> "%LOG%"
    start "" "%QQ_EXE%"
    ping -n 31 127.0.0.1 >nul
) else (
    echo [%date% %time%] QQ already running >> "%LOG%"
)

rem ---- SnowLuma 网关（WebUI 5099 / OneBot 3000+3001）----
netstat -ano | findstr "LISTENING" | findstr ":5099" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting SnowLuma >> "%LOG%"
    wscript.exe //nologo "%H%start-snowluma-hidden.vbs"
    ping -n 31 127.0.0.1 >nul
) else (
    echo [%date% %time%] SnowLuma already running >> "%LOG%"
)

rem ---- 跟随 DSH 的随机端口（每次启动都变）----
powershell -NoProfile -ExecutionPolicy Bypass -File "%H%sync-dsh-port.ps1" >nul 2>&1

rem ---- 桥接 ----
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { $_.CommandLine -match 'bridge\.js' }) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting qq-bridge >> "%LOG%"
    wscript.exe //nologo "%H%start-bridge-hidden.vbs"
) else (
    echo [%date% %time%] qq-bridge already running >> "%LOG%"
)

rem ---- 共享记忆同步循环（每 20 分钟）----
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | Where-Object { $_.CommandLine -match 'sync-memory-loop' }) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting memory sync >> "%LOG%"
    wscript.exe //nologo "%H%start-memory-sync-hidden.vbs"
) else (
    echo [%date% %time%] memory sync already running >> "%LOG%"
)

rem ---- 端口跟随（每 60 秒）----
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | Where-Object { $_.CommandLine -match 'follow-dsh-port' }) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting port follower >> "%LOG%"
    wscript.exe //nologo "%H%start-port-follow-hidden.vbs"
) else (
    echo [%date% %time%] port follower already running >> "%LOG%"
)

rem ---- 健康看门狗（每 2 分钟，缺什么补什么）----
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | Where-Object { $_.CommandLine -match 'watchdog-loop' }) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] starting health watchdog >> "%LOG%"
    wscript.exe //nologo "%H%start-bot-health-hidden.vbs"
) else (
    echo [%date% %time%] health watchdog already running >> "%LOG%"
)

echo [%date% %time%] done >> "%LOG%"
endlocal
