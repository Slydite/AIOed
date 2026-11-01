Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir

Dim pyPath
If fso.FileExists(scriptDir & "\.venv\Scripts\pythonw.exe") Then
    pyPath = """" & scriptDir & "\.venv\Scripts\pythonw.exe"""
ElseIf fso.FileExists(scriptDir & "\.venv\Scripts\python.exe") Then
    pyPath = """" & scriptDir & "\.venv\Scripts\python.exe"""
Else
    pyPath = "pythonw.exe"
End If

WshShell.Run pyPath & " """ & scriptDir & "\main.py""", 0, False

Set WshShell = Nothing
Set fso = Nothing
