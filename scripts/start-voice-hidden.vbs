' Hidden launcher for the voice service daemons (MiniMax / MiMo / RVC).
' ASCII only: cscript reads .vbs as ANSI, UTF-8 comments break parsing.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "F:\feiyu-voice"

sh.Run """F:\feiyu-voice\venv-cv\Scripts\python.exe"" ""F:\feiyu-voice\minimax-tts-daemon.py""", 0, False
sh.Run """F:\feiyu-voice\venv-cv\Scripts\python.exe"" ""F:\feiyu-voice\mimo-tts-daemon.py""", 0, False
sh.Run """F:\RVC\venv\Scripts\python.exe"" ""F:\RVC\voice-daemon.py""", 0, False
