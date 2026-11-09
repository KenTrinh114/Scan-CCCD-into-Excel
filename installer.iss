[Setup]
AppId={{8F9A2C41-5E3B-4A91-9D12-C78123456789}
AppName=App quét CCCD cho Nger ❤️
AppVersion=2026.11.09.0659
AppPublisher=Internal HR Tool
DefaultDirName={autopf}\CCCDScanner
DisableDirPage=no
DisableProgramGroupPage=no
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=CCCD_Scanner_Setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\app_icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài màn hình chính (Desktop)"; GroupDescription: "Tùy chọn thêm:"

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
