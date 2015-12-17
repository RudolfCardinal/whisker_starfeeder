@echo off

set VIRTUALENVDIR=%1

echo "==============================================================================="
echo "Prerequisites
echo "==============================================================================="
echo " - Download and install Python 3.x"
echo "   e.g."
echo "       https://www.python.org/downloads/windows/"
echo "       > Latest Python 3 Release - Python 3.5.1 [REQUIRES VISTA]"
echo "       > Windows x86 executable installer"
echo "   or"
echo "       Python 3.4.4rc1 > Download Windows x86 MSI installer [OLDER WINDOWS]"
echo "   After installation, Python should be at C:\Python34\python.exe or similar."

set PYTHONDIR=C:\Python34
set PYTHON=%PYTHONDIR%\python.exe
set PIP=%PYTHONDIR%\Scripts\pip.exe
set VENV=%PYTHONDIR%\Tools\Scripts\pyvenv.py

set THIS_SCRIPT_DIR=%~dp0
set PROJECT_BASE=%THIS_SCRIPT_DIR%\..

echo "==============================================================================="
echo "Creating virtual environment at %VIRTUALENVDIR%"
echo "==============================================================================="
%VENV% %VIRTUALENVDIR%

echo "==============================================================================="
echo "Activate our virtual environment, %VIRTUALENVDIR%"
echo "==============================================================================="
%VIRTUALENVDIR%\Scripts\activate.bat

# ... now "python", "pip", etc. refer to the virtual environment
echo "python is now: `which python`"
python --version
echo "pip is now: `which pip`"
pip --version
reassure "OK"

echo "==============================================================================="
echo "7. Install dependencies"
echo "==============================================================================="
pip install -r $PROJECT_BASE/requirements.txt
reassure "OK"

reassure "--- Virtual environment installed successfully"
