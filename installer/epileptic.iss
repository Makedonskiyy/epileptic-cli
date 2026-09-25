; EpilepticCLI Inno Setup installer - per-user install, no admin needed.
; Build: iscc /DMyAppVersion="0.2.0" installer/epileptic.iss

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

[Setup]
AppId={{B4E51C0D-E91C-4A1F-9B2E-6F3A7C2D9E51}
AppName=EpilepticCLI
AppVersion={#MyAppVersion}
AppPublisher=Epileptic Hurts
AppPublisherURL=https://github.com/Makedonskiyy/epileptic-cli
AppSupportURL=https://github.com/Makedonskiyy/epileptic-cli/issues
DefaultDirName={localappdata}\Programs\EpilepticCLI
DefaultGroupName=EpilepticCLI
OutputDir=..\dist
OutputBaseFilename=EpilepticCLI-Setup
PrivilegesRequired=lowest
Compression=lzma2
SolidCompression=yes
ChangesEnvironment=yes
WizardStyle=modern
UninstallDisplayName=EpilepticCLI

[Files]
Source: "..\dist\epileptic.exe"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "addtopath"; Description: "Add EpilepticCLI to your PATH"; Flags: checkedonce

[Icons]
Name: "{group}\EpilepticCLI"; Filename: "{app}\epileptic.exe"
Name: "{group}\Uninstall EpilepticCLI"; Filename: "{uninstallexe}"

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath

[Code]
{ remove our dir from PATH on uninstall }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  PathData, AppDir: string;
begin
  if CurUninstallStep = usUninstall then
  begin
    AppDir := ExpandConstant('{app}');
    if RegQueryStringValue(HKCU, 'Environment', 'Path', PathData) then
    begin
      StringChangeEx(PathData, ';' + AppDir, '', True);
      RegWriteExpandStringValue(HKCU, 'Environment', 'Path', PathData);
    end;
  end;
end;
