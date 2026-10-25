#ifndef AppVersion
  #error Pass /DAppVersion using packaging/build.ps1
#endif
[Setup]
AppId={{DB9D604D-0D93-495C-9875-127B5D10797F}
AppName=Subloom NVIDIA acceleration
AppVersion={#AppVersion}
AppPublisher=Subloom contributors
DefaultDirName={localappdata}\Subloom\runtimes\gpu
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installers
OutputBaseFilename=Subloom-NVIDIA-Setup-{#AppVersion}
SetupIconFile=Subloom.ico
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
LicenseFile=..\licenses\NVIDIA-CUDA-EULA.txt
UninstallDisplayName=Subloom NVIDIA acceleration

[Files]
Source: "..\.tools\runtime\gpu\*"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\licenses\NVIDIA-CUDA-EULA.html"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\licenses\NVIDIA-CUDA-EULA.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\licenses\whisper.cpp\LICENSE"; DestDir: "{app}\licenses"; DestName: "Whisper-MIT.txt"; Flags: ignoreversion
