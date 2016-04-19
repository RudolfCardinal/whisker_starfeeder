#!/usr/bin/env python

"""
Smart quotes also transforms "--" to en dash, "---" to em dash, and "..."
to ellipsis. See http://docutils.sourceforge.net/docs/user/config.html

For RST title conventions, see
    http://docs.openstack.org/contributor-guide/rst-conv/titles.html

"""

import os
import shutil
import subprocess
import sys
import tempfile
if sys.version_info[0] < 3:
    raise AssertionError("Need Python 3")

PYTHON = sys.executable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
DOC_DIR = os.path.join(PROJECT_BASE_DIR, 'doc')
# BUILD_DIR = os.path.join(PROJECT_BASE_DIR, 'build')
DIST_DIR = os.path.join(PROJECT_BASE_DIR, 'dist')
CSS = os.path.join(DOC_DIR, 'stylesheets', 'voidspace.css')
RST = os.path.join(DOC_DIR, 'manual.rst')
HTML = os.path.join(DOC_DIR, 'temp.html')
PDF = os.path.join(DIST_DIR, 'manual.pdf')
RST2HTML = shutil.which('rst2html.py')
if RST2HTML is None:
    raise AssertionError('Need rst2html.py (use: pip install docutils)')
WKHTMLTOPDF = shutil.which('wkhtmltopdf')
if WKHTMLTOPDF is None:
    raise AssertionError('Need wkhtmltopdf')

# wkhtmltopdf is tricky:
# 1. I've not managed to get wkhtmltopdf to cope with images unless it has a
#    disk file, rather than stdin.
# 2. Also, the filename MUST end in '.html'.
# 3. Other filenames are interpreted relative to the file's location, not
#    the current directory.

if __name__ == '__main__':
    os.makedirs(DIST_DIR, exist_ok=True)
    htmlfile = tempfile.NamedTemporaryFile(
        suffix='.html', dir=DOC_DIR, delete=False)
    print("""
Making documentation
- Source: {RST}
- Intermediary: {htmlfile}
- Destination: {PDF}
    """.format(
        RST=RST,
        htmlfile=htmlfile.name,
        PDF=PDF,
    ))
    subprocess.call([
        PYTHON, RST2HTML,
        '--stylesheet={}'.format(CSS),
        '--smart-quotes', 'yes',
        RST
    ], stdout=htmlfile)
    htmlfile.close()
    print("filename ", htmlfile.name)
    subprocess.call([WKHTMLTOPDF, htmlfile.name, PDF])
    os.remove(htmlfile.name)
