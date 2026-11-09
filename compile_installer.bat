@echo off
setlocal

set "PYTHON_EXE=python"
if exist ".\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=.\.venv\Scripts\python.exe"
)

echo Syncing version metadata...
"%PYTHON_EXE%" update_version.py
if %errorlevel% neq 0 (
    echo [ERROR] Failed to update version metadata!
    exit /b %errorlevel%
)

echo Compiling Inno Setup installer...

if exist "F:\InnoSetup\ISCC.exe" (
    "F:\InnoSetup\ISCC.exe" installer.iss
) else (
    if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
    ) else (
        iscc.exe installer.iss
    )
)

if %errorlevel% neq 0 (
    echo [ERROR] Inno Setup compilation failed!
    exit /b %errorlevel%
)

echo.
echo ============================================================
echo Installer compiled successfully!
echo Output located in: installer_output\CCCD_Scanner_Setup.exe
echo ============================================================
endlocal
