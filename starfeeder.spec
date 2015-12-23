# -*- mode: python -*-

"""
PyInstaller .spec file for Starfeeder.

This should be executed from the project base directory.
To check that directory references are working, break hooks/hook-serial.py
and ensure the build crashes.
"""

block_cipher = None

a = Analysis(['starfeeder/main.py'],
             binaries=None,
             datas=[
                # tuple is: source path/glob, destination directory
                # (regardless of what the docs suggest) and '' seems to
                # work for "the root directory"
                ('starfeeder/alembic.ini', ''),
                ('starfeeder/alembic/env.py', 'alembic'),
                ('starfeeder/alembic/versions/*.py', 'alembic/versions'),
             ],
             hiddenimports=[],
             hookspath=['hooks'],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             strip_paths=2)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='starfeeder',
          debug=False,
          strip=False,
          upx=True,
          console=False)  # NB!
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='starfeeder')
