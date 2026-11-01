Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")

' 1. Desktop Shortcut
desktopPath = WshShell.SpecialFolders("Desktop")
Set shortcutDesktop = WshShell.CreateShortcut(desktopPath & "\AIOed Dashboard.lnk")
shortcutDesktop.TargetPath = "wscript.exe"
shortcutDesktop.Arguments = """" & scriptDir & "\open_dashboard.vbs"""
shortcutDesktop.WorkingDirectory = scriptDir
shortcutDesktop.IconLocation = scriptDir & "\icon.ico,0"
shortcutDesktop.Description = "Open AIOed DeepCool LM360 Dashboard"
shortcutDesktop.Save

' 2. Start Menu Programs Shortcut
On Error Resume Next
programsPath = WshShell.SpecialFolders("Programs")
If fso.FolderExists(programsPath) Then
    Set shortcutStart = WshShell.CreateShortcut(programsPath & "\AIOed Dashboard.lnk")
    shortcutStart.TargetPath = "wscript.exe"
    shortcutStart.Arguments = """" & scriptDir & "\open_dashboard.vbs"""
    shortcutStart.WorkingDirectory = scriptDir
    shortcutStart.IconLocation = scriptDir & "\icon.ico,0"
    shortcutStart.Description = "Open AIOed DeepCool LM360 Dashboard"
    shortcutStart.Save
End If
On Error GoTo 0

Set shortcutDesktop = Nothing
Set shortcutStart = Nothing
Set WshShell = Nothing
Set fso = Nothing
