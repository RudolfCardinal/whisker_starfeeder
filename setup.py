#!/usr/bin/env python
# setup.py

"""
Starfeeder setup file

"""
# http://python-packaging-user-guide.readthedocs.org/en/latest/distributing/
# http://jtushman.github.io/blog/2013/06/17/sharing-code-across-applications-with-python/  # noqa

from setuptools import setup  # , find_packages
from codecs import open
from os import path
# import pip
# from pip.req import parse_requirements

from starfeeder.version import VERSION

here = path.abspath(path.dirname(__file__))

# -----------------------------------------------------------------------------
# Get the long description from the README file
# -----------------------------------------------------------------------------
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

# -----------------------------------------------------------------------------
# Get the requirements from the requirements file
# -----------------------------------------------------------------------------
# http://stackoverflow.com/questions/14399534
# https://github.com/juanpabloaj/pip-init/issues/11
# reqfile = path.join(here, 'requirements.txt')
# install_reqs = parse_requirements(reqfile, session=pip.download.PipSession())
# reqs = [str(ir.req) if ir.req else str(ir.link) for ir in install_reqs]
# ... RNC modification: for github ones, the .req is None but .link works
# ... no, we have to use fancy stuff for the github ones;
#     http://stackoverflow.com/questions/18026980

# -----------------------------------------------------------------------------
# setup args
# -----------------------------------------------------------------------------
setup(
    name='whisker_starfeeder',

    version=VERSION,

    description='Whisker Starfeeder (starling RFID/balance reader)',
    long_description=long_description,

    # The project's main homepage.
    url='http://www.whiskercontrol.com/',

    # Author details
    author='Rudolf Cardinal',
    author_email='rudolf@pobox.com',

    # Choose your license
    license='GNU General Public License v3 or later (GPLv3+)',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Science/Research',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',  # noqa

        'Natural Language :: English',

        'Operating System :: OS Independent',

        'Programming Language :: Python :: 3',
        # 'Programming Language :: Python :: 3.2',
        # 'Programming Language :: Python :: 3.3',
        # 'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',  # PyQt5 requires 3.5
        'Programming Language :: Python :: 3 :: Only',

        'Topic :: System :: Hardware',
        'Topic :: System :: Networking',
    ],

    keywords='whisker rfid weigh balance starling',

    packages=['starfeeder'],

    install_requires=[
        # ---------------------------------------------------------------------
        # Standard PyPI packages
        # ---------------------------------------------------------------------
        'alembic>=0.8.3',  # migration tool for sqlalchemy
        'arrow',  # better datetime
        'attrdict',  # dictionaries with attribute-style access
        'bitstring>=3.1.4',  # manipulation of binary numbers
        # 'PySide==1.2.4',  # Python interface to Qt
        'PyQt5>=5.7',  # Python interface to Qt
        'pyserial>=3.2.1',  # serial port library
        'six>=1.10.0',  # Python 2/3 compatibility library
        'SQLAlchemy>=1.0.12',  # database ORM
        # 'typing==3.5.2.2',  # part of stdlib in Python 3.5, but not 3.4
        'whisker>=0.3.5',  # Whisker client library

        # ---------------------------------------------------------------------
        # Database connections (SQLite is built in)
        # ---------------------------------------------------------------------
        # MySQL:
        'PyMySQL>=0.7.2',

        # SQL Server / ODBC route:
        'pyodbc>=3.0.10',

        # PostgreSQL:
        'psycopg2>=2.6.1',

        # ---------------------------------------------------------------------
        # Specials: development versions
        # ---------------------------------------------------------------------
        # 'pyserial==3.0b1',

        # ---------------------------------------------------------------------
        # For development only
        # ---------------------------------------------------------------------
        # 'PyInstaller==3.1.1',
        # 'colorama',
        # 'docutils==0.12',  # documentation generation tools
        # 'git+https://github.com/pyinstaller/pyinstaller@93d25e563e49f88f5977afd9b6e26cb34bfb5efa',  # PyInstaller=3.1.dev0+93d25e5  # noqa
    ],
    dependency_links=[
        # ---------------------------------------------------------------------
        # PySerial development version
        # ---------------------------------------------------------------------
        # We browse at https://github.com/pyserial/pyserial
        # We want the commit 3e02f7052747521a21723a618dccf303065da732
        # We want the tarball
        # The API is:
        #   GET /repos/:owner/:repo/:archive_format/:ref
        #   - https://developer.github.com/v3/repos/contents/#get-archive-link
        # or
        #   https://github.com/user/project/archive/commit.zip
        #   - http://stackoverflow.com/questions/17366784
        # or
        #   http://github.com/usr/repo/tarball/tag
        # That gets us:
        #   https://github.com/pyserial/pyserial/tarball/3e02f7052747521a21723a618dccf303065da732  # noqa
        # We label it with "#egg=pyserial-3.0b1" for setup.py's benefit
        #   http://stackoverflow.com/questions/3472430
        # Final answer:

        # 'http://github.com/pyserial/pyserial/tarball/3e02f7052747521a21723a618dccf303065da732#egg=pyserial-3.0b1',  # noqa

        # ---------------------------------------------------------------------
        # MySQL Connector/Python
        # ---------------------------------------------------------------------
        # 'https://cdn.mysql.com/Downloads/Connector-Python/mysql-connector-python-2.1.3.tar.gz',  # MySQL Connector/Python  # noqa
    ],
    # YOU MUST ALSO USE THE "--process-dependency-links" FLAG.

    entry_points={
        'console_scripts': [
            # Format is 'script=module:function".
            'starfeeder=starfeeder.main:main',
            'starfeeder_mimic_rfid_reader=starfeeder.test_mimic_rfid_reader:main',  # noqa
            'starfeeder_mimic_balance=starfeeder.test_mimic_balance:main',
        ],
    },
)
