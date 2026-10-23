#define MyAppName "BlachCalc"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Izo-Technika"
#define MyAppExeName "BlachCalc.exe"

[Setup]
AppId={{25D1C2F7-5676-4E1D-804C-52E65CECF33E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\BlachCalc
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=release
OutputBaseFilename=BlachCalc-Setup
SetupIconFile=BlachCalc.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
CloseApplications=yes
SetupLogging=yes
Compression=lzma2
SolidCompression=yes

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "Utwórz ikonę na pulpicie"; GroupDescription: "Dodatkowe ikony:"

[Files]
Source: "dist\BlachCalc\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\BlachCalc"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\BlachCalc\Odinstaluj BlachCalc"; Filename: "{uninstallexe}"
Name: "{autodesktop}\BlachCalc"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Uruchom BlachCalc"; Flags: postinstall nowait skipifsilent
