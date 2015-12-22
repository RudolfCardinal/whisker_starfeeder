@echo off

set DEFAULTPYTHONDIR=C:\Python34

if "%~1" == "" (
    echo Syntax:
    echo    install_virtualenv.bat VIRTUALENVDIR [PYTHONDIR]
    echo Default for PYTHONDIR: %DEFAULTPYTHONDIR%
    exit /b
) else (
    set VIRTUALENVDIR=%1
)
if "%~2" == "" (
    set PYTHONDIR=C:\Python34
) else (
    set PYTHONDIR=%2
)

echo ===============================================================================
echo Prerequisites
echo ===============================================================================
echo - Download and install Python 3.x
echo   e.g.
echo       https://www.python.org/downloads/windows/
echo       > Latest Python 3 Release - Python 3.5.1 [REQUIRES VISTA]
echo       > Windows x86 executable installer
echo   or
echo       Python 3.4.4rc1 > Download Windows x86 MSI installer [OLDER WINDOWS]
echo   After installation, Python should be at C:\Python34\python.exe or similar.

echo ===============================================================================
echo Finding Python/Pip
echo ===============================================================================
set PYTHON=%PYTHONDIR%\python.exe
set PIP=%PYTHONDIR%\Scripts\pip.exe
set PYVENV=%PYTHONDIR%\Tools\Scripts\pyvenv.py

set THIS_SCRIPT_DIR=%~dp0
rem ... will have trailing slash
set PROJECT_BASE=%THIS_SCRIPT_DIR%..

echo python: %PYTHON%
echo pip: %PIP%
echo pyvenv.py: %PYVENV%
echo PROJECT_BASE: %PROJECT_BASE%

rem (A) pyvenv
set VENVTOOL=%PYVENV%

rem (B) virtualenv
rem echo ===============================================================================
rem echo Ensuring virtualenv is installed
rem echo ===============================================================================
rem %PIP% install virtualenv
rem set VIRTUALENV=%PYTHONDIR%\Scripts\virtualenv.exe
rem echo virtualenv: %VIRTUALENV%
rem set VENVTOOL=%VIRTUALENV%

echo ===============================================================================
echo Creating virtual environment at %VIRTUALENVDIR%
echo ===============================================================================
%VENVTOOL% %VIRTUALENVDIR%

echo ===============================================================================
echo Activate our virtual environment, %VIRTUALENVDIR%
echo ===============================================================================
call %VIRTUALENVDIR%\Scripts\activate.bat

python --version
pip --version

echo ===============================================================================
echo Install dependencies
echo ===============================================================================
pip install -r %PROJECT_BASE%\requirements.txt

echo --- Virtual environment installed successfully
