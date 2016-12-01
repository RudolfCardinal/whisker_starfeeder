# -*- mode: python -*-

"""
PyInstaller .spec file for Starfeeder.

This should be executed from the project base directory.
To check that directory references are working, break hooks/hook-serial.py
and ensure the build crashes.

Run with:

    # activate virtual environment firsrt
    # install locally first with pip install -e .

    pyinstaller starfeeder.spec --clean [--log-level DEBUG]

"""

import distutils
import platform
import os

# BROKEN in virtualenv # SITE_PACKAGES = site.getsitepackages()[0]
SITE_PACKAGES = distutils.sysconfig.get_python_lib()

WINDOWS = platform.system() == 'Windows'
binaries = []
if WINDOWS:
    QT_DLL_STEMS = ['Qt5Svg', 'Qt5Gui', 'Qt5Core', 'Qt5PrintSupport',
                    'Qt5Network']
    QT_DLL_DIR = os.path.join(SITE_PACKAGES, 'PyQt5', 'Qt', 'bin')
    for _stem in QT_DLL_STEMS:
        _name = _stem + '.dll'
        _fullpath = os.path.join(QT_DLL_DIR, _name)
        binaries.append((_name, _fullpath, 'BINARY'))

block_cipher = None

a = Analysis(
    ['starfeeder/main.py'],
    binaries=binaries,
    datas=[
        # tuple is: source path/glob, destination directory
        # (regardless of what the docs suggest) and '' seems to
        # work for "the root directory"
        ('dist/manual.pdf', ''),
        ('starfeeder/alembic.ini', ''),
        ('starfeeder/alembic/env.py', 'alembic'),
        ('starfeeder/alembic/versions/*.py', 'alembic/versions'),
    ],
    hiddenimports=[
        # (1) Database-specific backends (loaded by SQLAlchemy depending on URL)
        #     are hidden. So we want the following. But:
        # (2) These are CASE-SENSITIVE and are the names used by Python during
        #     imports (not, for example, the camel-case version used in PyPI).

        'pymysql',  # MySQL
        'pyodbc',  # PyODBC, and thus many things
        'psycopg2',  # PostgreSQL
        # SQLite is part of the standard library
    ],
    hookspath=['hooks'],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher
    # strip_paths=2
)
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='starfeeder',
    debug=False,
    strip=False,
    upx=True,
    console=False  # NB!
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='starfeeder'
)
