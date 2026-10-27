#define MyAppName "BlachCalc"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "Izo-Technika"
#define MyAppExeName "BlachCalc.exe"
#define MyAppURL "https://github.com/knowosinski/BlachCalc"

[Setup]
AppId={{25D1C2F7-5676-4E1D-804C-52E65CECF33E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
VersionInfoVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\BlachCalc
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
UsePreviousAppDir=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=release
OutputBaseFilename=BlachCalc-Setup
SetupIconFile=BlachCalc.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
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
Name: "{autoprograms}\{#MyAppName}\BlachCalc"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppName}\Odinstaluj BlachCalc"; Filename: "{uninstallexe}"
Name: "{autodesktop}\BlachCalc"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Uruchom BlachCalc"; Flags: postinstall nowait

[Code]
function InitializeUninstall: Boolean;
begin
  Result := UninstallSilent or (MsgBox(
    'Odinstalować BlachCalc?' + #13#10#13#10 +
    'Zapisane oferty i baza danych NIE zostaną usunięte.',
    mbConfirmation, MB_YESNO) = IDYES);
end;
