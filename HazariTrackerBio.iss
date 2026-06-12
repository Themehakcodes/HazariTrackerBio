; ─────────────────────────────────────────────────────────────────────────────
; HazariTrackerBio.iss  —  Inno Setup 6 installer script
;
; Builds:  HazariTrackerBio-vX.Y.Z-Setup.exe
;
; What this installer does automatically (no manual driver download needed):
;   1. Installs HazariTracker Bio EXE + all bundled DLLs
;   2. Copies Mantra SDK DLLs (MANTRA.MFS100.dll, iengine_ansi_iso.dll, MFS100Dll.dll)
;   3. Detects Windows version + CPU arch and silently installs the correct
;      Mantra MFS100 USB kernel driver via DPInst.exe /LM /Q
; ─────────────────────────────────────────────────────────────────────────────

#define MyAppName      "HazariTracker Bio"
; MyAppVersion is injected by publish.ps1 via:  ISCC /DMyAppVersion=X.Y.Z
; Fallback (used if compiled manually without /D flag):
#ifndef MyAppVersion
  #define MyAppVersion  "1.0.1"
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
; Minimum Windows version: Windows 10
MinVersion=10.0
; Privileges — required for kernel driver installation
PrivilegesRequired=admin
; Uninstall
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
SetupIconFile=icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}";     GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon";  Description: "Launch at Windows startup";   GroupDescription: "Startup:";             Flags: unchecked

; ─────────────────────────────────────────────────────────────────────────────
; Files
; ─────────────────────────────────────────────────────────────────────────────
[Files]
; ── Main application (PyInstaller one-folder build) ──────────────────────────
Source: "{#MyDistFolder}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Mantra SDK DLLs (from bundled drivers\ folder in repo) ───────────────────
Source: "drivers\MANTRA.MFS100.dll";    DestDir: "{app}"; Flags: ignoreversion
Source: "drivers\iengine_ansi_iso.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "drivers\MFS100Dll.dll";        DestDir: "{app}"; Flags: ignoreversion

; ── Mantra kernel driver files — Win10 x64 ───────────────────────────────────
Source: "drivers\MFS100Driver\Win-10-X64\*"; DestDir: "{tmp}\MFS100Driver\Win-10-X64"; Flags: ignoreversion skipifsourcedoesntexist

; ── Mantra kernel driver files — Win10 x86 ───────────────────────────────────
Source: "drivers\MFS100Driver\Win-10-X86\*"; DestDir: "{tmp}\MFS100Driver\Win-10-X86"; Flags: ignoreversion skipifsourcedoesntexist

; ── Mantra kernel driver files — Win7/8 x64 ──────────────────────────────────
Source: "drivers\MFS100Driver\Win-7-8-X64\*"; DestDir: "{tmp}\MFS100Driver\Win-7-8-X64"; Flags: ignoreversion skipifsourcedoesntexist

; ── Mantra kernel driver files — Win7/8 x86 ──────────────────────────────────
Source: "drivers\MFS100Driver\Win-7-8-X86\*"; DestDir: "{tmp}\MFS100Driver\Win-7-8-X86"; Flags: ignoreversion skipifsourcedoesntexist

; ─────────────────────────────────────────────────────────────────────────────
; Icons / Shortcuts
; ─────────────────────────────────────────────────────────────────────────────
[Icons]
Name: "{group}\{#MyAppName}";               Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";         Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}";         Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Registry]
Root: HKLM; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey

[Run]
; ── Silently install MFS100 kernel driver (correct arch) after main install ──
Filename: "{tmp}\MFS100Driver\Win-10-X64\DPInst.exe"; Parameters: "/LM /Q /F"; StatusMsg: "Installing Mantra MFS100 USB driver (64-bit)..."; Check: IsWin10AndX64; Flags: waituntilterminated runhidden
Filename: "{tmp}\MFS100Driver\Win-10-X86\DPInst.exe"; Parameters: "/LM /Q /F"; StatusMsg: "Installing Mantra MFS100 USB driver (32-bit)..."; Check: IsWin10AndNotX64; Flags: waituntilterminated runhidden

; ── Launch the app after install ─────────────────────────────────────────────
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%n%nThe Mantra MFS100 fingerprint sensor driver will be installed AUTOMATICALLY — no separate download required.%n%nClick Next to continue.

; ─────────────────────────────────────────────────────────────────────────────
; Code — helper functions for arch/OS detection
; ─────────────────────────────────────────────────────────────────────────────
[Code]

// Returns True if running on Windows 10/11 and 64-bit CPU
function IsWin10AndX64(): Boolean;
begin
  Result := IsWin64();
end;

// Returns True if running on Windows 10/11 and 32-bit CPU
function IsWin10AndNotX64(): Boolean;
begin
  Result := not IsWin64();
end;

// ── Pre-install check ─────────────────────────────────────────────────────────
function InitializeSetup(): Boolean;
var
  dotNetMsg: String;
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
    warningMsg  := warningMsg + dotNetMsg;
  end;

  if showWarning then
  begin
    MsgBox('WARNING — Missing Prerequisites:'#13#10#13#10 + warningMsg, mbInformation, MB_OK);
  end;

  // NOTE: Mantra MFS100 driver is now bundled and will be installed automatically.
  // No separate driver download is required.
end;
