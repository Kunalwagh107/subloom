#ifndef AppVersion
  #error Pass /DAppVersion using packaging/build.ps1
#endif
[Setup]
AppId={{F575CD9A-8647-42B8-981F-99F00B33D772}
AppName=Subloom
AppVersion={#AppVersion}
AppPublisher=Subloom contributors
DefaultDirName={localappdata}\Programs\Subloom
DefaultGroupName=Subloom
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installers
OutputBaseFilename=Subloom-Setup-{#AppVersion}
SetupIconFile=Subloom.ico
UninstallDisplayIcon={app}\Subloom.exe
LicenseFile=..\LICENSE
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes
UninstallDisplayName=Subloom

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\portable\{#AppVersion}\Subloom\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Subloom"; Filename: "{app}\Subloom.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Subloom"; Filename: "{app}\Subloom.exe"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\Subloom.exe"; Description: "Open Subloom"; Flags: nowait postinstall skipifsilent

; Models, sessions and optional GPU support live separately in LocalAppData.
; Uninstalling the app deliberately preserves the user's recordings and edits.
