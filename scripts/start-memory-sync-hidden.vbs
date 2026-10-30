' Hidden launcher for the shared-memory sync loop (no taskbar window).
' ASCII only: cscript reads .vbs as ANSI, UTF-8 comments break parsing.
Set sh = CreateObject("WScript.Shell")
sh.Run """%~dp0..\sync-memory-loop.cmd""", 0, False
