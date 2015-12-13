#!/bin/bash

THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
PROJECT_BASE=`readlink -m "$THIS_SCRIPT_DIR/.."`

cd "$PROJECT_BASE"
mkdir -p thirdparty/pyinstaller
cd thirdparty/pyinstaller
wget https://github.com/pyinstaller/pyinstaller/releases/download/3.0/PyInstaller-3.0.tar.gz
tar xvf PyInstaller-3.0.tar.gz
cd PyInstaller-3.0
python3 setup.py install
