; ─────────────────────────────────────────────────────────────────────────────
; HazariTrackerBio.iss  —  Inno Setup 6 installer script
;
; Builds:  HazariTrackerBio-vX.Y.Z-Setup.exe
;
; Prerequisites on BUILD machine:
;   • Inno Setup 6   https://jrsoftware.org/isinfo.php
;   • PyInstaller build must already be done (.\build.ps1)
;
; Prerequisites on TARGET machine (bundled/checked by installer):
;   • Windows 10 / 11  (x86 or x64)
;   • .NET Framework 4.x   — ships with Windows 10+
;   • Mantra MFS100 driver  — installer will WARN if not found
; ─────────────────────────────────────────────────────────────────────────────

#define MyAppName      "HazariTracker Bio"
; MyAppVersion is injected by publish.ps1 via:  ISCC /DMyAppVersion=X.Y.Z
; Fallback (used if compiled manually without /D flag):
#ifndef MyAppVersion
  #define MyAppVersion  "1.0.0"
#endif
#define MyAppPublisher "Themehakcodes"
#define MyAppURL       "https://github.com/Themehakcodes/HazariTrackerBio"
#define MyAppExeName   "HazariTrackerBio.exe"
#define MyDistFolder   "dist\HazariTrackerBio-v" + MyAppVersion
#define MyOutputDir    "dist"

[Setup]
AppId={{A3F2E8C1-9B4D-4E7A-B2F6-1C8D3E5F7A9B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf32}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Output
OutputDir={#MyOutputDir}
OutputBaseFilename=HazariTrackerBio-v{#MyAppVersion}-Setup
; Compression
Compression=lzma2/ultra64
SolidCompression=yes
; Architecture — 32-bit installer (Mantra SDK is x86)
ArchitecturesInstallIn64BitMode=
; UI
WizardStyle=modern
WizardResizable=yes
; Minimum Windows version: Windows 10
MinVersion=10.0
; Privileges — install per-machine so the driver DLLs land in Program Files
PrivilegesRequired=admin
; Uninstall
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}";     GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon";  Description: "Launch at Windows startup";   GroupDescription: "Startup:";             Flags: unchecked

[Files]
; ── Main application (PyInstaller one-folder build) ──────────────────────────
Source: "{#MyDistFolder}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; -- Mantra MFS100 DLLs from repo root (if present) ----------------------------
Source: "MANTRA.MFS100.dll";    DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "iengine_ansi_iso.dll"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; -- Mantra DLLs from standard Mantra install path (if on build machine) -------
Source: "C:\Program Files\Mantra\MFS100\Driver\MFS100Test\MANTRA.MFS100.dll";    DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "C:\Program Files\Mantra\MFS100\Driver\MFS100Test\iengine_ansi_iso.dll"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}";               Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";         Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}";         Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Registry]
; Add to PATH so the app can be launched from cmd (optional)
Root: HKLM; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Messages]
; Custom welcome message
WelcomeLabel2=This will install [name/ver] on your computer.%n%nMANTRA MFS100 fingerprint device driver must be installed separately before using the application.%n%nClick Next to continue.

[Code]
// ─────────────────────────────────────────────────────────────────────────────
// Pre-install checks
// ─────────────────────────────────────────────────────────────────────────────
function InitializeSetup(): Boolean;
var
  dotNetMsg: String;
  driverMsg: String;
  warningMsg: String;
  showWarning: Boolean;
begin
  Result := True;
  showWarning := False;
  warningMsg  := '';

  // Check .NET Framework 4.x
  if not RegKeyExists(HKLM, 'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full') then
  begin
    dotNetMsg := '.NET Framework 4.x was not detected on this machine.'#13#10 +
                 'The application requires it to communicate with the Mantra MFS100 SDK.'#13#10#13#10 +
                 'Please install .NET Framework 4.8 from Microsoft before running the app.';
    showWarning := True;
    warningMsg  := warningMsg + dotNetMsg + #13#10#13#10;
  end;

  // Check Mantra driver registry key (written by the Mantra installer)
  if not RegKeyExists(HKLM, 'SOFTWARE\Mantra Softech India Pvt. Ltd.\MFS100') and
     not RegKeyExists(HKLM, 'SOFTWARE\WOW6432Node\Mantra Softech India Pvt. Ltd.\MFS100') then
  begin
    driverMsg := 'Mantra MFS100 driver was not detected.'#13#10 +
                 'Fingerprint scanning will NOT work until the driver is installed.'#13#10#13#10 +
                 'Download the driver from: https://www.mantratec.com/resources/Software-Resources/MFS100-Software';
    showWarning := True;
    warningMsg  := warningMsg + driverMsg;
  end;

  if showWarning then
  begin
    MsgBox('WARNING — Missing Prerequisites:'#13#10#13#10 + warningMsg, mbInformation, MB_OK);
  end;
end;
