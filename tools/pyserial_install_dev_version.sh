#!/bin/bash

THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
PROJECT_BASE=`readlink -m "$THIS_SCRIPT_DIR/.."`

cd "$PROJECT_BASE"
mkdir -p thirdparty
cd thirdparty
git clone https://github.com/pyserial/pyserial/
cd pyserial
python3 setup.py install
