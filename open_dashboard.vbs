Option Explicit

Dim fso, scriptDir, WshShell, url
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir

url = "http://localhost:5220"

Function IsServiceRunning()
    IsServiceRunning = False
    On Error Resume Next
    Dim http
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts 200, 200, 200, 400
    http.open "GET", url & "/api/status", False
    http.send
    If Err.Number = 0 Then
        If http.status = 200 Then
            IsServiceRunning = True
        End If
    End If
    Set http = Nothing
    On Error GoTo 0
End Function

If Not IsServiceRunning() Then
    ' Start background daemon silently
    WshShell.Run "wscript.exe """ & scriptDir & "\run_background.vbs""", 0, False

    ' Active polling loop: wait for service to bind port and respond with 200 OK
    Dim waitedMs, maxWaitMs, isReady
    waitedMs = 0
    maxWaitMs = 15000
    isReady = False

    Do While waitedMs < maxWaitMs
        WScript.Sleep 250
        waitedMs = waitedMs + 250
        If IsServiceRunning() Then
            isReady = True
            Exit Do
        End If
    Loop

    If Not isReady Then
        MsgBox "AIOed Display Service could not be contacted after startup." & vbCrLf & vbCrLf & _
               "Please check 'aioed.log' in the project directory for details.", vbExclamation, "AIOed Dashboard"
        WScript.Quit 1
    End If
End If

' Service is confirmed ready; open browser to dashboard
WshShell.Run url

Set WshShell = Nothing
Set fso = Nothing
