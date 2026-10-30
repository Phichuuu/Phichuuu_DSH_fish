' Hidden launcher for the QQ bot health watchdog (watchdog-loop.cmd).
' ASCII only: cscript reads .vbs as ANSI, UTF-8 comments break parsing.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "%~dp0.."
sh.Run "cmd.exe /c ""%~dp0..\watchdog-loop.cmd""", 0, False
