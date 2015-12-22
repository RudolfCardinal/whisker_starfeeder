@echo off

set THIS_SCRIPT_DIR=%~dp0
rem ... will have trailing slash
set PROJECT_BASE=%THIS_SCRIPT_DIR%..

cd "%PROJECT_BASE%"

echo "Deleting old distribution..."
rmdir /s build
rmdir /s dist

echo "Building new distribution..."
echo ==========================================================================
pyinstaller starfeeder.spec --clean --log-level=INFO

echo ==========================================================================
echo The dist/starfeeder/ directory should contain everything you need.
echo Run with: dist/starfeeder/starfeeder
echo Look for warnings in: build/starfeeder/warnstarfeeder.txt
