; Inno Setup script - builds AirPlayReceiver-Setup.exe
; It installs the app, adds the firewall rule ONCE at install time (so the app
; itself opens instantly with no prompt), and creates shortcuts + an uninstaller.
;
; HOW TO USE:
;   1. Build the app folder first:  powershell -File .\build_portable.ps1
;      (produces the AirPlayMirror-portable folder next to this script)
;   2. Install Inno Setup (free): https://jrsoftware.org/isdl.php
;   3. Open this file in Inno Setup and click Build > Compile (or press F9).
;   4. Share the resulting Output\AirPlayReceiver-Setup.exe

#define AppName "AirPlay Receiver"
#define AppVersion "1.0.0"
#define ExeName "AirPlayMirror.exe"
#define FwRule "AirPlay Receiver (UxPlay)"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Open source (GPL-3.0)
DefaultDirName={autopf}\AirPlay Receiver
DefaultGroupName=AirPlay Receiver
UninstallDisplayIcon={app}\{#ExeName}
OutputBaseFilename=AirPlayReceiver-Setup
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
; everything the build produced (the exe, its _internal deps, runtime\, etc.)
Source: "AirPlayMirror-portable\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\AirPlay Receiver"; Filename: "{app}\{#ExeName}"
Name: "{group}\Uninstall AirPlay Receiver"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AirPlay Receiver"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupFlags: unchecked

[Run]
; Add the firewall rule now (installer is already elevated) so the app never prompts.
Filename: "{sys}\netsh.exe"; \
  Parameters: "advfirewall firewall add rule name=""{#FwRule}"" dir=in action=allow program=""{app}\runtime\bin\uxplay.exe"" enable=yes profile=private,domain"; \
  Flags: runhidden
; Offer to launch at the end.
Filename: "{app}\{#ExeName}"; Description: "Launch AirPlay Receiver"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Clean the firewall rule out on uninstall.
Filename: "{sys}\netsh.exe"; \
  Parameters: "advfirewall firewall delete rule name=""{#FwRule}"""; \
  Flags: runhidden
