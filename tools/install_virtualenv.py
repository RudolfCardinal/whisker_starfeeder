#!/usr/bin/env python

import argparse
import os
import platform
import shutil
import subprocess
import sys

if sys.version_info[0] < 3:
    raise AssertionError("Need Python 3")

DESCRIPTION = """
Make a new virtual environment.
Please specify the directory in which the virtual environment should be
created. For example, for a testing environment
    {script} ~/MYPROJECT_virtualenv

or for a production environment:
    sudo --user=www-data XDG_CACHE_HOME=/usr/share/MYPROJECT/.cache \\
        {script} /usr/share/MYPROJECT/virtualenv
""".format(script=os.path.basename(__file__))

LINUX = platform.system() == 'Linux'

PYTHON = sys.executable
PYTHONBASE = os.path.basename(PYTHON)
PIP = shutil.which('pip3')

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
PIP_REQ_FILE = os.path.join(PROJECT_BASE_DIR, 'requirements.txt')
DEBIAN_REQ_FILE = os.path.join(PROJECT_BASE_DIR, 'requirements-ubuntu.txt')

SEP = "=" * 79


def title(msg):
    print(SEP)
    print(msg)
    print(SEP)


def require_debian_package(package):
    if not LINUX:
        return
    proc = subprocess.Popen(
        ['dpkg', '-l', package],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.communicate()
    retcode = proc.returncode
    if retcode == 0:
        return
    print("You must install the package {package}. On Ubuntu, use the command:"
          "\n"
          "    sudo apt-get install {package}".format(package=package))
    sys.exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("virtualenv", help="New virtual environment directory")
    parser.add_argument("--virtualenv_minimum_version", default="13.1.2",
                        help="Minimum version of virtualenv tool")
    args = parser.parse_args()

    if LINUX:
        VENV_TOOL = 'virtualenv'
        VENV_PYTHON = os.path.join(args.virtualenv, 'bin', 'python')
        VENV_PIP = os.path.join(args.virtualenv, 'bin', 'pip')
        ACTIVATE = "source " + os.path.join(args.virtualenv, 'bin', 'activate')
    else:  # Windows
        VENV_TOOL = 'venv'  # pyvenv.py, but you can use "-m venv"
        VENV_PYTHON = os.path.join(args.virtualenv, 'Scripts', 'python.exe')
        VENV_PIP = os.path.join(args.virtualenv, 'Scripts', 'pip.exe')
        ACTIVATE = "call " + os.path.join(args.virtualenv, 'Scripts',
                                          'activate')

    if LINUX:
        title("Prerequisites, from " + DEBIAN_REQ_FILE)
        print("XDG_CACHE_HOME: {}".format(os.environ.get('XDG_CACHE_HOME', None)))
        with open(DEBIAN_REQ_FILE) as f:
            for line in f:
                package = line.strip()
                if package:
                    require_debian_package(package)
        print('OK')

        title("Ensuring virtualenv is installed for system"
              " Python ({})".format(PYTHON))
        subprocess.check_call(
            [PIP, 'install',
             'virtualenv>={}'.format(args.virtualenv_minimum_version)])
        print('OK')

    title(
        "Using system Python ({}) and virtualenv tool ({}) to make {}".format(
            PYTHON, VENV_TOOL, args.virtualenv))
    subprocess.check_call(
        [PYTHON, '-m', VENV_TOOL, args.virtualenv])
    print('OK')

    title("Checking version of tools within new virtualenv")
    print(VENV_PYTHON)
    subprocess.check_call([VENV_PYTHON, '--version'])
    print(VENV_PIP)
    subprocess.check_call([VENV_PIP, '--version'])

    title("Use pip within the new virtualenv to install dependencies")
    subprocess.check_call([VENV_PIP, 'install', '-r', PIP_REQ_FILE])
    print('OK')
    print('--- Virtual environment installed successfully')

    print("""
To activate the virtual environment, use
    {ACTIVATE}

    """.format(ACTIVATE=ACTIVATE))
