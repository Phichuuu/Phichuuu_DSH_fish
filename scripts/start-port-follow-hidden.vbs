' Hidden launcher for the fast DSH port follower (no taskbar window).
' ASCII only: cscript reads .vbs as ANSI, UTF-8 comments break parsing.
Set sh = CreateObject("WScript.Shell")
sh.Run """%~dp0..\follow-dsh-port.cmd""", 0, False
