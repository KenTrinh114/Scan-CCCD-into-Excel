@echo off
setlocal
echo ============================================================
echo [1/4] Downloading WeChat QR Caffe Models...
echo ============================================================
call .\.venv\Scripts\python.exe setup_models.py
if %errorlevel% neq 0 (
    echo Error: Failed to setup WeChat models.
    exit /b %errorlevel%
)

echo.
echo ============================================================
echo [2/4] Running Unit Tests...
echo ============================================================
call .\.venv\Scripts\pytest.exe tests/
if %errorlevel% neq 0 (
    echo Error: Unit tests failed.
    exit /b %errorlevel%
)

echo.
echo ============================================================
echo [3/4] Building Standalone Folder (--onedir) via PyInstaller...
echo ============================================================
call .\.venv\Scripts\pyinstaller.exe --noconfirm --onedir --windowed ^
    --name "CCCDScanner" ^
    --workpath "F:\Codes\CCCD for Nger\build" ^
    --distpath "F:\Codes\CCCD for Nger\dist" ^
    --add-data "assets\wechat_models;assets\wechat_models" ^
    --exclude-module matplotlib ^
    --exclude-module scipy ^
    --exclude-module pandas ^
    --exclude-module PyQt5 ^
    --exclude-module PySide6 ^
    main.py

if %errorlevel% neq 0 (
    echo Error: PyInstaller build failed.
    exit /b %errorlevel%
)

echo.
echo ============================================================
echo [4/4] Compiling Zero-Admin Windows Installer (.exe)...
echo ============================================================
call compile_installer.bat
if %errorlevel% neq 0 (
    echo Error: Inno Setup compilation failed.
    exit /b %errorlevel%
)

echo.
echo ============================================================
echo ALL BUILDS COMPLETED SUCCESSFULLY!
echo Final Installer: installer_output\CCCD_Scanner_Setup.exe
echo ============================================================
endlocal
