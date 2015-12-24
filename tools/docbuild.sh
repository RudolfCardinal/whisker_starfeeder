#!/bin/bash

set -e

THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
PROJECT_BASE=`readlink -m "$THIS_SCRIPT_DIR/.."`
DOCDIR="$PROJECT_BASE/doc"
DISTDIR="$PROJECT_BASE/dist"

mkdir -p "$DISTDIR"

CSS="$DOCDIR/stylesheets/voidspace.css"
RST="$DOCDIR/manual.txt"
HTML="$DOCDIR/manual.html"
PDF="$DISTDIR/manual.pdf"

rst2html.py --stylesheet="$CSS" --smart-quotes yes "$RST" > "$HTML"
# Smart quotes also transforms "--" to en dash, "---" to em dash, and "..."
# to ellipsis. See http://docutils.sourceforge.net/docs/user/config.html

wkhtmltopdf "$HTML" "$PDF"

# For title conventions, see
# http://docs.openstack.org/contributor-guide/rst-conv/titles.html
