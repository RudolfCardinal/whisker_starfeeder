#!/bin/bash

# Exit on any error
set -e

#==============================================================================
# Functions
#==============================================================================

error() {
    # http://stackoverflow.com/questions/5947742/how-to-change-the-output-color-of-echo-in-linux/5947788#5947788
    echo "$(tput setaf 1)$(tput bold)$@$(tput sgr0)"  # red
    # 1 red, 2 green, 3 ?dark yellow, 4 blue, 5 magenta, 6 cyan, 7 white
}

warn() {
    echo "$(tput setaf 3)$(tput bold)$@$(tput sgr0)"  # yellow
}

reassure() {
    echo "$(tput setaf 2)$(tput bold)$@$(tput sgr0)"  # green
}

bold() {
    echo "$(tput bold)$@$(tput sgr0)"
}

require_debian_package() {
    echo "Checking for Debian package: $1"
    dpkg -l $1 >/dev/null && return
    warn "You must install the package $1. On Ubuntu, use the command:"
    warn "    sudo apt-get install $1"
    exit 1
}

#==============================================================================
# Parameters
#==============================================================================

# Set the VIRTUALENVDIR environment variable from the first argument
# ... minus any trailing slashes
#     http://stackoverflow.com/questions/9018723/what-is-the-simplest-way-to-remove-a-trailing-slash-from-each-parameter
shopt -s extglob
export VIRTUALENVDIR="${1%%+(/)}"

if [ "$VIRTUALENVDIR" == "" ]; then
    error "Invalid parameters"
    cat << END_HEREDOC
Syntax:
    $0 VIRTUALENVDIR

Please specify the directory in which the virtual environment should be
created. For example, for a testing environment
    $0 ~/MYPROJECT_virtualenv

or for a production environment:
    sudo --user=www-data XDG_CACHE_HOME=/usr/share/MYPROJECT/.cache $0 /usr/share/MYPROJECT/virtualenv

END_HEREDOC
    exit 1
fi

#==============================================================================
# Variables
#==============================================================================

#------------------------------------------------------------------------------
# Software
#------------------------------------------------------------------------------
# Select Python executable:
PYTHON=$(which python3.4)
# And pip executable
PIP=$(which pip3)
# Select minimum version of virtualenv:
VENV_VERSION=13.1.2

#------------------------------------------------------------------------------
# Directories
#------------------------------------------------------------------------------
VIRTUALENVDIR=`readlink -m $VIRTUALENVDIR`  # removes any trailing /
THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
PROJECT_BASE=`readlink -m "$THIS_SCRIPT_DIR/.."`

PYTHONBASE=`basename $PYTHON`
# SITE_PACKAGES="$VIRTUALENVDIR/lib/$PYTHONBASE/site-packages"

#==============================================================================
# Main
#==============================================================================

bold "==============================================================================="
bold "1. Prerequisites, from $PROJECT_BASE/requirements-ubuntu.txt"
bold "==============================================================================="
#echo "whoami: `whoami`"
#echo "HOME: $HOME"
echo "XDG_CACHE_HOME: $XDG_CACHE_HOME"
while read package; do
    require_debian_package $package
done <"$PROJECT_BASE/requirements-ubuntu.txt"
reassure "OK"

bold "==============================================================================="
bold "2. Ensuring virtualenv is installed for system Python ($PYTHON)"
bold "==============================================================================="
$PIP install "virtualenv>=$VENV_VERSION"
reassure "OK"

bold "==============================================================================="
bold "3. Using system Python ($PYTHON) and virtualenv to make $VIRTUALENVDIR"
bold "==============================================================================="
"$PYTHON" -m virtualenv "$VIRTUALENVDIR"
reassure "OK"

bold "==============================================================================="
bold "4. Activate our virtual environment, $VIRTUALENVDIR"
bold "==============================================================================="
source "$VIRTUALENVDIR/bin/activate"
# ... now "python", "pip", etc. refer to the virtual environment
echo "python is now: `which python`"
python --version
echo "pip is now: `which pip`"
pip --version
reassure "OK"

bold "==============================================================================="
bold "5. Install dependencies"
bold "==============================================================================="
pip install -r $PROJECT_BASE/requirements.txt
reassure "OK"

reassure "--- Virtual environment installed successfully"
