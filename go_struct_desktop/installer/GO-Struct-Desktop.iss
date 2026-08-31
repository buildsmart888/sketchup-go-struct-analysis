; Windows installer definition. tools\build_windows_installer.ps1 passes the
; release values so this source remains suitable for future beta builds.
#ifndef SourceRoot
  #define SourceRoot ".."
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef ReleaseLabel
  #define ReleaseLabel "Beta 0.1"
#endif
#ifndef PayloadRoot
  #define PayloadRoot "{#SourceRoot}\release\payload"
#endif

[Setup]
AppId={{B82A2B41-C007-44AC-AC8C-87CED3E56EA6}
AppName=GO Struct Desktop
AppVersion={#AppVersion}
AppVerName=GO Struct Desktop {#ReleaseLabel}
AppPublisher=BuildSmart888
AppPublisherURL=https://github.com/buildsmart888/sketchup-go-struct-analysis
DefaultDirName={autopf}\BuildSmart888\GO Struct Desktop
DefaultGroupName=GO Struct Desktop
DisableProgramGroupPage=yes
OutputDir={#SourceRoot}\release\installer
OutputBaseFilename=GO-Struct-Desktop-Beta-0.1-Setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName=GO Struct Desktop {#ReleaseLabel}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#PayloadRoot}\GO-Struct-Desktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\docs\MANUAL.html"; DestDir: "{app}\Manual"; Flags: ignoreversion
Source: "{#SourceRoot}\docs\images\*"; DestDir: "{app}\Manual\images"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\src\go_struct_desktop\assets\icons\*.ico"; DestDir: "{app}\icons"; Flags: ignoreversion

[Icons]
Name: "{group}\GO Struct Frame"; Filename: "{app}\GO-Struct-Desktop.exe"; Parameters: "--workspace frame"; WorkingDir: "{userdocs}"; IconFilename: "{app}\icons\frame.ico"
Name: "{group}\GO Struct Beam"; Filename: "{app}\GO-Struct-Desktop.exe"; Parameters: "--workspace beam"; WorkingDir: "{userdocs}"; IconFilename: "{app}\icons\beam.ico"
Name: "{group}\GO Struct Truss"; Filename: "{app}\GO-Struct-Desktop.exe"; Parameters: "--workspace truss"; WorkingDir: "{userdocs}"; IconFilename: "{app}\icons\truss.ico"
Name: "{group}\Manual"; Filename: "{app}\Manual\MANUAL.html"; WorkingDir: "{app}\Manual"
Name: "{autodesktop}\GO Struct Frame"; Filename: "{app}\GO-Struct-Desktop.exe"; Parameters: "--workspace frame"; WorkingDir: "{userdocs}"; IconFilename: "{app}\icons\frame.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\GO-Struct-Desktop.exe"; Parameters: "--workspace frame"; Description: "Launch GO Struct Frame"; Flags: nowait postinstall skipifsilent
