Option Explicit

Dim fso, scriptDir, WshShell
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")

' 1. Desktop Shortcut (Launches Dashboard UI)
On Error Resume Next
Dim desktopPath, shortcutDesktop
desktopPath = WshShell.SpecialFolders("Desktop")
If fso.FolderExists(desktopPath) Then
    Set shortcutDesktop = WshShell.CreateShortcut(desktopPath & "\AIOed Dashboard.lnk")
    shortcutDesktop.TargetPath = "wscript.exe"
    shortcutDesktop.Arguments = """" & scriptDir & "\open_dashboard.vbs"""
    shortcutDesktop.WorkingDirectory = scriptDir
    shortcutDesktop.IconLocation = scriptDir & "\icon.ico,0"
    shortcutDesktop.Description = "Open AIOed DeepCool LM360 Dashboard"
    shortcutDesktop.Save
    Set shortcutDesktop = Nothing
End If

' 2. Start Menu Programs Shortcut
Dim programsPath, shortcutStart
programsPath = WshShell.SpecialFolders("Programs")
If fso.FolderExists(programsPath) Then
    Set shortcutStart = WshShell.CreateShortcut(programsPath & "\AIOed Dashboard.lnk")
    shortcutStart.TargetPath = "wscript.exe"
    shortcutStart.Arguments = """" & scriptDir & "\open_dashboard.vbs"""
    shortcutStart.WorkingDirectory = scriptDir
    shortcutStart.IconLocation = scriptDir & "\icon.ico,0"
    shortcutStart.Description = "Open AIOed DeepCool LM360 Dashboard"
    shortcutStart.Save
    Set shortcutStart = Nothing
End If

' 3. Windows Startup Folder Shortcut (Silent Background Autostart)
Dim startupPath, shortcutStartup
startupPath = WshShell.SpecialFolders("Startup")
If fso.FolderExists(startupPath) Then
    Set shortcutStartup = WshShell.CreateShortcut(startupPath & "\AIOed Background Service.lnk")
    shortcutStartup.TargetPath = "wscript.exe"
    shortcutStartup.Arguments = """" & scriptDir & "\run_background.vbs"""
    shortcutStartup.WorkingDirectory = scriptDir
    shortcutStartup.IconLocation = scriptDir & "\icon.ico,0"
    shortcutStartup.Description = "AIOed DeepCool LM360 Background Service"
    shortcutStartup.Save
    Set shortcutStartup = Nothing
End If
On Error GoTo 0

Set WshShell = Nothing
Set fso = Nothing
