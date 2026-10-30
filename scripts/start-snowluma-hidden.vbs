' Hidden launcher for SnowLuma (no taskbar window).
' ASCII only: cscript reads .vbs as ANSI, UTF-8 comments break parsing.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "F:\SnowLuma"
sh.Run """F:\SnowLuma\launcher.bat""", 0, False
