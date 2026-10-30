' Hidden launcher for qq-bridge (no taskbar window).
' ASCII only: cscript reads .vbs as ANSI, UTF-8 comments break parsing.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "F:\qq-bridge"
sh.Run """C:\Program Files\nodejs\node.exe"" ""F:\qq-bridge\src\bridge.js""", 0, False
