Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir

Dim isRunning
isRunning = False

On Error Resume Next
Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
http.setTimeouts 500, 500, 500, 1000
http.open "GET", "http://localhost:5220/api/status", False
http.send
If http.status = 200 Then
    isRunning = True
End If
Set http = Nothing
On Error GoTo 0

If Not isRunning Then
    WshShell.Run "wscript.exe """ & scriptDir & "\run_background.vbs""", 0, False
    WScript.Sleep 1500
End If

WshShell.Run "http://localhost:5220"

Set WshShell = Nothing
Set fso = Nothing
