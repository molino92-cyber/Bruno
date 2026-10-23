; Inno Setup 6. Gerar após o PyInstaller: ISCC.exe packaging\installer.iss
#ifndef AppVersion
  #define AppVersion "1.3.1"
#endif

[Setup]
AppId={{04F02C86-2819-47DE-AF11-79C3DCE0EB4B}
AppName=Doce Ateliê
AppVersion={#AppVersion}
AppPublisher=Doce Ateliê
DefaultDirName={localappdata}\Programs\DoceAtelie
DefaultGroupName=Doce Ateliê
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\instalador
OutputBaseFilename=DoceAtelie-Instalador-{#AppVersion}-Windows-x64
SetupIconFile=..\assets\doce-atelie.ico
UninstallDisplayIcon={app}\DoceAtelie.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "..\dist\DoceAtelie\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Doce Ateliê"; Filename: "{app}\DoceAtelie.exe"; AppUserModelID: "DoceAtelie.Pedidos"
Name: "{autodesktop}\Doce Ateliê"; Filename: "{app}\DoceAtelie.exe"; Tasks: desktopicon
Name: "{group}\Desinstalar Doce Ateliê"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\DoceAtelie.exe"; Description: "Abrir Doce Ateliê"; Flags: nowait postinstall skipifsilent

; Sem UninstallDelete: dados em LOCALAPPDATA\DoceAtelie são preservados.

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN DoceAtelie-Lembretes /F"; Flags: runhidden; RunOnceId: "remover-lembretes"
