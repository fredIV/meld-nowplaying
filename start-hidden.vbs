' Launches the overlay server with no console window.
' Stop it later with Task Manager (pythonw.exe) or by running stop.bat.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run """.venv\Scripts\pythonw.exe"" server.py", 0, False
