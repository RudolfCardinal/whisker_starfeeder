#!/bin/bash

warn() {
    # http://stackoverflow.com/questions/5947742/how-to-change-the-output-color-of-echo-in-linux/5947788#5947788
    echo "$(tput setaf 1)$@$(tput sgr0)"
}

# Were we called or sourced? Several ways to tell.
[[ x"${BASH_SOURCE[0]}" != x"$0" ]]&&SOURCED=1||SOURCED=0;
if (( $SOURCED == 0 )); then
    warn "Execute this as 'source $0' or '. $0' or it will do nothing"
    exit 1
fi

# Where are we?
THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
DBFILE=`readlink -m "$THIS_SCRIPT_DIR/../test_db.sqlite3"`

export STARFEEDER_DATABASE_URL=sqlite:////$DBFILE
