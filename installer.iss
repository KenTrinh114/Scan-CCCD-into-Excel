[Setup]
AppId={{8F9A2C41-5E3B-4A91-9D12-C78123456789}
AppName=App quét CCCD cho Nger ❤️
AppVersion=2.2.0
AppPublisher=Internal HR Tool
DefaultDirName={code:GetDefaultTargetDir|{autopf}\CCCDScanner}
UsePreviousAppDir=yes
DisableDirPage=auto
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=CCCD_Scanner_Setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\app_icon.ico
CloseApplications=yes
CloseApplicationsFilter=CCCDScanner.exe
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài màn hình chính (Desktop)"; GroupDescription: "Tùy chọn thêm:"

[InstallDelete]
; Clean up old internal binaries before extracting new files to prevent duplicate/orphaned dependencies
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\CCCDScanner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "uninstall.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\App quét CCCD cho Nger ❤️"; Filename: "{app}\CCCDScanner.exe"; Tasks: desktopicon
Name: "{autoprograms}\App quét CCCD cho Nger ❤️"; Filename: "{app}\CCCDScanner.exe"
Name: "{autoprograms}\Gỡ cài đặt App quét CCCD cho Nger"; Filename: "{uninstallexe}"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Run]
Filename: "{app}\CCCDScanner.exe"; Description: "Mở App quét CCCD cho Nger ❤️ ngay bây giờ"; Flags: nowait postinstall skipifsilent

[Code]
var
  ExistingInstallDir: String;
  ExistingVersion: String;
  IsUpgradeInstall: Boolean;

function IsAppProcessRunning(const ExeFileName: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/c tasklist /fi "imagename eq ' + ExeFileName + '" | find /i "' + ExeFileName + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

function FindInstalledAppDir(var FoundVersion: String): String;
var
  RegKey: String;
  InstallPath: String;
  VerStr: String;
begin
  Result := '';
  FoundVersion := '';
  RegKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8F9A2C41-5E3B-4A91-9D12-C78123456789}_is1';

  // 1. Check HKCU (Per-user installation - default lowest privileges)
  if RegQueryStringValue(HKCU, RegKey, 'Inno Setup: App Path', InstallPath) or
     RegQueryStringValue(HKCU, RegKey, 'InstallLocation', InstallPath) then
  begin
    if (InstallPath <> '') and DirExists(InstallPath) then
    begin
      RegQueryStringValue(HKCU, RegKey, 'DisplayVersion', VerStr);
      FoundVersion := VerStr;
      Result := InstallPath;
      Exit;
    end;
  end;

  // 2. Check HKLM 64-bit (Machine-wide installation on 64-bit OS)
  if RegQueryStringValue(HKLM64, RegKey, 'Inno Setup: App Path', InstallPath) or
     RegQueryStringValue(HKLM64, RegKey, 'InstallLocation', InstallPath) then
  begin
    if (InstallPath <> '') and DirExists(InstallPath) then
    begin
      RegQueryStringValue(HKLM64, RegKey, 'DisplayVersion', VerStr);
      FoundVersion := VerStr;
      Result := InstallPath;
      Exit;
    end;
  end;

  // 3. Check HKLM 32-bit (Machine-wide installation on 32-bit / WoW64)
  if RegQueryStringValue(HKLM32, RegKey, 'Inno Setup: App Path', InstallPath) or
     RegQueryStringValue(HKLM32, RegKey, 'InstallLocation', InstallPath) then
  begin
    if (InstallPath <> '') and DirExists(InstallPath) then
    begin
      RegQueryStringValue(HKLM32, RegKey, 'DisplayVersion', VerStr);
      FoundVersion := VerStr;
      Result := InstallPath;
      Exit;
    end;
  end;
end;

function GetDefaultTargetDir(Param: String): String;
begin
  if (ExistingInstallDir <> '') and DirExists(ExistingInstallDir) then
    Result := ExistingInstallDir
  else
    Result := ExpandConstant('{autopf}\CCCDScanner');
end;

function InitializeSetup(): Boolean;
var
  PromptMsg: String;
begin
  Result := True;

  // 1. Check if application is currently running; prompt user to close it
  while IsAppProcessRunning('CCCDScanner.exe') do
  begin
    if MsgBox('Phần mềm "App quét CCCD cho Nger" hiện đang được mở.' + #13#10#13#10 +
              'Vui lòng đóng ứng dụng trước khi tiếp tục để quá trình cập nhật diễn ra an toàn.',
              mbConfirmation, MB_RETRYCANCEL) = IDCANCEL then
    begin
      Result := False;
      Exit;
    end;
  end;

  // 2. Detect previous installation to update in-place instead of creating duplicate folder
  ExistingInstallDir := FindInstalledAppDir(ExistingVersion);
  if ExistingInstallDir <> '' then
  begin
    IsUpgradeInstall := True;
    if ExistingVersion <> '' then
      PromptMsg := 'Phát hiện phiên bản cũ (v' + ExistingVersion + ') đã được cài đặt tại:' + #13#10 +
                   ExistingInstallDir + #13#10#13#10 +
                   'Trình cài đặt sẽ tự động cập nhật phiên bản mới trực tiếp vào thư mục này để tránh tạo thư mục trùng lặp.'
    else
      PromptMsg := 'Phát hiện ứng dụng đã được cài đặt tại:' + #13#10 +
                   ExistingInstallDir + #13#10#13#10 +
                   'Trình cài đặt sẽ tự động cập nhật phiên bản mới trực tiếp vào thư mục này để tránh tạo thư mục trùng lặp.';

    MsgBox(PromptMsg, mbInformation, MB_OK);
  end
  else
  begin
    IsUpgradeInstall := False;
  end;
end;
