@echo off
setlocal
chcp 65001 >nul
echo ============================================================
echo   GỠ CÀI ĐẶT PHẦN MỀM QUÉT QR CCCD SANG EXCEL
echo   UNINSTALL CCCD QR EXTRACTOR TO EXCEL
echo ============================================================
echo.

:: 1. Close any running instances of CCCDScanner
echo [1/4] Closing running application instances...
taskkill /F /IM CCCDScanner.exe >nul 2>&1

:: 2. Check for official Inno Setup uninstaller
set "UNINSTALLER="

:: Check current directory (if run from inside installed app folder)
if exist "%~dp0unins000.exe" set "UNINSTALLER=%~dp0unins000.exe"

:: Check standard User install folder
if not defined UNINSTALLER (
    if exist "%LOCALAPPDATA%\Programs\CCCDScanner\unins000.exe" (
        set "UNINSTALLER=%LOCALAPPDATA%\Programs\CCCDScanner\unins000.exe"
    )
)

:: Check Program Files (x86 / 64-bit) if installed with admin
if not defined UNINSTALLER (
    if exist "%ProgramFiles%\CCCDScanner\unins000.exe" (
        set "UNINSTALLER=%ProgramFiles%\CCCDScanner\unins000.exe"
    )
)
if not defined UNINSTALLER (
    if exist "%ProgramFiles(x86)%\CCCDScanner\unins000.exe" (
        set "UNINSTALLER=%ProgramFiles(x86)%\CCCDScanner\unins000.exe"
    )
)

if defined UNINSTALLER (
    echo [2/4] Running uninstaller: %UNINSTALLER%
    start /wait "" "%UNINSTALLER%" /SILENT
) else (
    echo [2/4] Uninstaller executable not found. Performing manual folder cleanup...
    if exist "%LOCALAPPDATA%\Programs\CCCDScanner" (
        rmdir /s /q "%LOCALAPPDATA%\Programs\CCCDScanner" >nul 2>&1
    )
)

:: 3. Clean up desktop and Start Menu shortcuts
echo [3/4] Removing Desktop and Start Menu shortcuts...
if exist "%USERPROFILE%\Desktop\App quét CCCD cho Nger ❤️.lnk" (
    del /f /q "%USERPROFILE%\Desktop\App quét CCCD cho Nger ❤️.lnk" >nul 2>&1
)
if exist "%USERPROFILE%\Desktop\Quét QR CCCD sang Excel.lnk" (
    del /f /q "%USERPROFILE%\Desktop\Quét QR CCCD sang Excel.lnk" >nul 2>&1
)
if exist "%PUBLIC%\Desktop\App quét CCCD cho Nger ❤️.lnk" (
    del /f /q "%PUBLIC%\Desktop\App quét CCCD cho Nger ❤️.lnk" >nul 2>&1
)
if exist "%PUBLIC%\Desktop\Quét QR CCCD sang Excel.lnk" (
    del /f /q "%PUBLIC%\Desktop\Quét QR CCCD sang Excel.lnk" >nul 2>&1
)
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\App quét CCCD cho Nger ❤️.lnk" (
    del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\App quét CCCD cho Nger ❤️.lnk" >nul 2>&1
)
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Quét QR CCCD sang Excel.lnk" (
    del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Quét QR CCCD sang Excel.lnk" >nul 2>&1
)
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Gỡ cài đặt App quét CCCD cho Nger.lnk" (
    del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Gỡ cài đặt App quét CCCD cho Nger.lnk" >nul 2>&1
)
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Gỡ cài đặt Quét QR CCCD.lnk" (
    del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Gỡ cài đặt Quét QR CCCD.lnk" >nul 2>&1
)

:: 4. Clean up user configuration files
echo [4/4] Removing saved user configuration files...
if exist "%LOCALAPPDATA%\CCCDScanner" (
    rmdir /s /q "%LOCALAPPDATA%\CCCDScanner" >nul 2>&1
)

echo.
echo ============================================================
echo   GỠ CÀI ĐẶT HOÀN TẤT!
echo   CCCD Scanner has been completely removed from your PC.
echo ============================================================
echo.
pause
endlocal
