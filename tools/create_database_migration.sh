#!/bin/bash

THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
PROJECT_BASE=`readlink -m "$THIS_SCRIPT_DIR/.."`

N_SEQUENCE_CHARS=4  # like Django

# Check syntax
if [ "$1" == "" ]; then
    echo "Syntax:"
    echo "   $0 \"comment\""
    exit 1
fi

# Find latest revision
CURRENT_SEQ=`find "$PROJECT_BASE/migrations/versions" -type f -name "*.py" -printf "%f\n" | cut -c 1-$N_SEQUENCE_CHARS | sort | tail -n 1`
# echo "Current sequence number: $CURRENT_SEQ"
if [ "$CURRENT_SEQ" = "" ]; then
    CURRENT_SEQ=0
fi
echo "Current sequence number: $CURRENT_SEQ"

# Add one
NEW_SEQ=$((CURRENT_SEQ + 1))
# Add leading zeros
printf -v NEW_SEQ "%0${N_SEQUENCE_CHARS}d" $NEW_SEQ
echo "    New sequence number: $NEW_SEQ"

export PYTHONPATH=$PROJECT_BASE
alembic revision --autogenerate -m $1 --rev-id $NEW_SEQ

# If it fails with "Can't locate revision identified by...", you might need to DROP the alembic_version table.
