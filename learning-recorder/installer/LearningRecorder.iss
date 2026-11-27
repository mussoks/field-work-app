; 학습 레코더 설치 프로그램 (Inno Setup 6)
;   iscc /DMyAppVersion=0.2.0 installer\LearningRecorder.iss
; 관리자 권한 없이 사용자 계정에 설치됩니다 (회사 PC 에서도 설치 가능).

#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
#endif
#define MyAppName "학습 레코더"
#define MyAppExe "LearningRecorder.exe"

[Setup]
AppId={{6B0E8C1A-3F7D-4E52-9C1B-7A4D2E9F51C3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppName}
DefaultDirName={autopf}\LearningRecorder
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=LearningRecorder-Setup-{#MyAppVersion}
SetupIconFile=..\src\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4
WizardStyle=modern
WizardSizePercent=110
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
CloseApplications=yes
RestartApplications=no

[Languages]
#ifexist "compiler:Languages\Korean.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
#else
Name: "english"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 작업:"
Name: "autostart"; Description: "Windows 시작 시 트레이에서 자동 실행 (단축키 바로 사용)"; GroupDescription: "추가 작업:"; Flags: unchecked

[Files]
Source: "..\dist\LearningRecorder\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\{#MyAppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "LearningRecorder"; ValueData: """{app}\{#MyAppExe}"" --minimized"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{#MyAppName} 실행하기"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#MyAppExe}"; Flags: runhidden; RunOnceId: "StopApp"

[Messages]
#ifexist "compiler:Languages\Korean.isl"
korean.WelcomeLabel2=ERP 업무 화면을 AI 학습용으로 녹화·캡쳐하는 [name/ver] 을(를) 설치해요.%n%n클릭 위치가 또렷하게 표시된 영상과 단계별 캡쳐, 학습 데이터(JSON)를 한 번에 만들 수 있어요.%n%n녹화·캡쳐 파일은 바탕화면의 [학습용캡쳐] 폴더에 저장돼요.
#endif
