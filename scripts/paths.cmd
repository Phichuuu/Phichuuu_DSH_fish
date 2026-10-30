@echo off
rem ===================================================================
rem  paths.cmd -- 所有本机路径都写在这里，其它脚本 call 它。
rem  改这一个文件就够了。
rem ===================================================================
rem  ASCII only: cmd.exe 按本地代码页读批处理，中文会乱码。

rem ---- 这个仓库在哪（默认就是本文件所在目录的上一级）----
if not defined REPO set "REPO=%~dp0.."

rem ---- 第三方：QQ 客户端 ----
if not defined QQ_EXE set "QQ_EXE=C:\Program Files\Tencent\QQNT\QQ.exe"

rem ---- 第三方：桥接 / 语音服务 / 模拟器 ----
if not defined BRIDGE_DIR  set "BRIDGE_DIR=F:\qq-bridge"
if not defined VOICE_DIR   set "VOICE_DIR=F:\feiyu-voice"
if not defined RVC_DIR     set "RVC_DIR=F:\RVC"
if not defined MUMU_DIR    set "MUMU_DIR=F:\MuMuPlayer"

rem ---- DSH 的用户目录 ----
if not defined DSH_HOME set "DSH_HOME=%USERPROFILE%\.dsh"

rem ---- 结语：谁 call 了这个文件，就能直接用上面的变量 ----
exit /b 0
