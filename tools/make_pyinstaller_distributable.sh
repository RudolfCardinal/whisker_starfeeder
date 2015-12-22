#!/bin/bash

set -e  # we don't want a "cd" failure to cause a dangerous rm

THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
PROJECT_BASE=`readlink -m "$THIS_SCRIPT_DIR/.."`

cd "$PROJECT_BASE"

echo "Deleting old distribution..."
rm -rf build/
rm -rf dist/
# NO, WE USE THIS NOW # rm -f starfeeder.spec

echo "Building new distribution..."
echo "========================================================================"
# pyinstaller starfeeder/main.py --name starfeeder --additional-hooks-dir="$PROJECT_BASE/hooks" --clean --log-level=DEBUG
pyinstaller starfeeder.spec --clean --log-level=INFO

echo "========================================================================"
echo "The dist/starfeeder/ directory should contain everything you need."
echo "Run with: dist/starfeeder/starfeeder"
echo "Look for warnings in: build/starfeeder/warnstarfeeder.txt"
