@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Network Switcher - Build

echo [1/4] Checking Python...
where py >nul 2>&1 && (set "PY=py -3") || (set "PY=python")
%PY% --version >nul 2>&1 || (
  echo  Python not found. Install it from python.org and tick "Add to PATH".
  pause & exit /b 1
)

echo [2/4] Installing build tools...
%PY% -m pip install --upgrade pip >nul
%PY% -m pip install --upgrade pyinstaller customtkinter pillow || (echo  pip failed & pause & exit /b 1)

echo [3/4] Building NetworkSwitcher.exe ...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin ^
  --name NetworkSwitcher --icon app.ico --add-data "app.ico;." ^
  --collect-data customtkinter netswitch.py || (echo  Build failed & pause & exit /b 1)

echo [4/4] Installing and creating desktop shortcut...
set "DEST=%LOCALAPPDATA%\Programs\NetworkSwitcher"
if not exist "%DEST%" mkdir "%DEST%"
taskkill /IM NetworkSwitcher.exe /F >nul 2>&1
copy /Y "dist\NetworkSwitcher.exe" "%DEST%\" >nul
copy /Y "app.ico" "%DEST%\" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Network Switcher.lnk'));" ^
  "$s.TargetPath='%DEST%\NetworkSwitcher.exe'; $s.WorkingDirectory='%DEST%'; $s.IconLocation='%DEST%\app.ico,0';" ^
  "$s.Description='Network Switcher - DTW ELBAYADH'; $s.Save()"

echo.
echo  Done.  EXE: %DEST%\NetworkSwitcher.exe
echo         Shortcut "Network Switcher" is on your desktop.
pause
