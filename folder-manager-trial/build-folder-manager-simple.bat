:: 哈利 / Simple Windows EXE build script for file-folder-manager
@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d %~dp0

echo [INFO] Checking Python...
set "PY_CMD="

call :try_launcher "py -3.13"
if defined PY_CMD goto python_ok
call :try_launcher "py -3.12"
if defined PY_CMD goto python_ok
call :try_launcher "py -3.11"
if defined PY_CMD goto python_ok
call :try_launcher "py -3.10"
if defined PY_CMD goto python_ok
call :try_launcher py
if defined PY_CMD goto python_ok
call :try_launcher python
if defined PY_CMD goto python_ok
call :try_launcher python3
if defined PY_CMD goto python_ok

echo [ERROR] No usable Python command found.
echo [TIP] Install Python 3.10 - 3.13 stable.
pause
exit /b 1

:python_ok
echo [INFO] Using command: %PY_CMD%
call %PY_CMD% --version
if %errorlevel% neq 0 (
  echo [ERROR] Python version check failed.
  pause
  exit /b 1
)

echo [INFO] Upgrading pip...
call %PY_CMD% -m pip install --upgrade pip
if %errorlevel% neq 0 (
  echo [ERROR] Failed to upgrade pip.
  pause
  exit /b 1
)

echo [INFO] Installing PyInstaller...
call %PY_CMD% -m pip install pyinstaller
if %errorlevel% neq 0 (
  echo [ERROR] Failed to install PyInstaller.
  pause
  exit /b 1
)

echo [INFO] Packaging EXE...
call %PY_CMD% -m PyInstaller --noconfirm --clean --windowed --onefile --name "WindowsFolderManager" file-folder-manager.py
if %errorlevel% neq 0 (
  echo [ERROR] Packaging failed.
  echo [TIP] Avoid Python 3.14 alpha / preview builds.
  pause
  exit /b 1
)

echo.
echo [OK] Build completed: dist\WindowsFolderManager.exe
echo.
pause
exit /b 0

:try_launcher
call %~1 --version >nul 2>nul
if errorlevel 1 exit /b 0
set "PY_CMD=%~1"
exit /b 0
