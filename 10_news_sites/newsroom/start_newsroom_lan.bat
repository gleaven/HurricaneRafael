@echo off
setlocal
cd /d "%~dp0"
title Coastal Bend Newsroom (shared network)
echo Starting the newsroom on the shared network. Participants use the address printed below.
echo.
set "PY="
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo Python 3.8 or newer is required and was not found.
  echo Install it from https://www.python.org/downloads/ ^(check "Add python.exe to PATH"^), then run this again.
  goto end
)
%PY% server.py --lan %*
:end
echo.
pause
