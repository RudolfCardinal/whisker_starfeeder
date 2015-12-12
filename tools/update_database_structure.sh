#!/bin/bash
THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
PROJECT_BASE=`readlink -m "$THIS_SCRIPT_DIR/.."`
export PYTHONPATH=$PROJECT_BASE

alembic upgrade head
