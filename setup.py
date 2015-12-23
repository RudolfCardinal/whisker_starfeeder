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
    name='starfeeder',

    version=VERSION,

    description='Whisker Starfeeder (starling RFID/balance reader)',
    long_description=long_description,

    # The project's main homepage.
    url='http://www.whiskercontrol.com/',

    # Author details
    author='Rudolf Cardinal',
    author_email='rudolf@pobox.com',

    # Choose your license
    license='Apache License 2.0',

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
        'License :: OSI Approved :: Apache Software License',

        'Natural Language :: English',

        'Operating System :: OS Independent',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
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
        'alembic==0.8.3',  # migration tool for sqlalchemy
        'bitstring==3.1.3',  # manipulation of binary numbers
        'PySide==1.2.4',  # Python interface to Qt
        'SQLAlchemy==1.0.9',  # database ORM
        # ---------------------------------------------------------------------
        # Specials: development versions
        # ---------------------------------------------------------------------
        'pyserial==3.0b1',
    ],
    dependency_links=[
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

        'http://github.com/pyserial/pyserial/tarball/3e02f7052747521a21723a618dccf303065da732#egg=pyserial-3.0b1',  # noqa
    ],
    # YOU MUST ALSO USE THE "--process-dependency-links" FLAG.

    entry_points={
        'console_scripts': [
            # Format is 'script=module:function".
            'starfeeder=starfeeder.main:main',
        ],
    },
)
