@echo off
setlocal

set "PYTHON_EXE=python"
if exist ".\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=.\.venv\Scripts\python.exe"
)

set "PYTEST_EXE=pytest"
if exist ".\.venv\Scripts\pytest.exe" (
    set "PYTEST_EXE=.\.venv\Scripts\pytest.exe"
)

set "PYINSTALLER_EXE=pyinstaller"
if exist ".\.venv\Scripts\pyinstaller.exe" (
    set "PYINSTALLER_EXE=.\.venv\Scripts\pyinstaller.exe"
)

echo ============================================================
echo [1/4] Stamping Deploy Version (Date and Time)...
echo ============================================================
"%PYTHON_EXE%" update_version.py
if %errorlevel% neq 0 (
    echo Error: Failed to stamp version.
    exit /b %errorlevel%
)

echo.
echo ============================================================
echo [2/4] Downloading WeChat QR Caffe Models...
echo ============================================================
"%PYTHON_EXE%" setup_models.py
if %errorlevel% neq 0 (
    echo Error: Failed to setup WeChat models.
    exit /b %errorlevel%
)

echo.
echo ============================================================
echo [3/4] Running Unit Tests...
echo ============================================================
"%PYTEST_EXE%" tests/
if %errorlevel% neq 0 (
    echo Error: Unit tests failed.
    exit /b %errorlevel%
)

echo.
echo ============================================================
echo [4/4] Building Standalone Folder (--onedir) via PyInstaller...
echo ============================================================
"%PYINSTALLER_EXE%" --noconfirm --onedir --windowed ^
    --name "CCCDScanner" ^
    --icon "assets\app_icon.ico" ^
    --workpath "F:\Codes\CCCD for Nger\build" ^
    --distpath "F:\Codes\CCCD for Nger\dist" ^
    --add-data "assets\wechat_models;assets\wechat_models" ^
    --add-data "assets\app_icon.ico;assets" ^
    --add-data "assets\app_icon.png;assets" ^
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
echo Build complete! Output located in dist\CCCDScanner\
endlocal
