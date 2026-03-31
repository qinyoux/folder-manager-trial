:: 哈利 / Windows EXE build script for file-folder-manager
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
echo [TIP] Preferred: Python 3.10 - 3.13 stable
echo [TIP] Current packaging tool is not compatible with some Python 3.14 alpha builds.
pause
exit /b 1

:python_ok
echo [INFO] Using command: %PY_CMD%
call %PY_CMD% --version
if %errorlevel% neq 0 (
  echo [ERROR] Python version check failed unexpectedly.
  pause
  exit /b 1
)

echo [INFO] Creating virtual environment...
call %PY_CMD% -m venv .venv-build
if %errorlevel% neq 0 (
  echo [ERROR] Failed to create virtual environment.
  echo [TIP] Python may be missing venv or the installation is incomplete.
  pause
  exit /b 1
)

if not exist ".venv-build\Scripts\python.exe" (
  echo [ERROR] .venv-build\Scripts\python.exe was not created.
  pause
  exit /b 1
)

call .venv-build\Scripts\activate.bat
if %errorlevel% neq 0 (
  echo [ERROR] Failed to activate virtual environment.
  pause
  exit /b 1
)

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
  echo [ERROR] Failed to upgrade pip.
  pause
  exit /b 1
)

echo [INFO] Installing PyInstaller...
pip install pyinstaller
if %errorlevel% neq 0 (
  echo [ERROR] Failed to install PyInstaller.
  pause
  exit /b 1
)

echo [INFO] Packaging EXE...
pyinstaller --noconfirm --clean --windowed --onefile --name "WindowsFolderManager" file-folder-manager.py
if %errorlevel% neq 0 (
  echo [ERROR] Packaging failed.
  echo [TIP] Python 3.14 alpha is not supported by current PyInstaller.
  echo [TIP] Use Python 3.10 / 3.11 / 3.12 / 3.13 stable instead.
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
