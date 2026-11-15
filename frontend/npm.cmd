@echo off
setlocal

set "NODE_PACKAGE_ROOT=%LOCALAPPDATA%\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe"
set "NODE_DIR="
for /d %%D in ("%NODE_PACKAGE_ROOT%\node-v*-win-x64") do set "NODE_DIR=%%~fD"

if defined NODE_DIR if exist "%NODE_DIR%\npm.cmd" (
  set "PATH=%NODE_DIR%;%PATH%"
  call "%NODE_DIR%\npm.cmd" %*
  exit /b %errorlevel%
)

set "NPM_COMMAND="
for /f "delims=" %%N in ('where.exe npm.cmd 2^>nul') do (
  if /I not "%%~fN"=="%~f0" set "NPM_COMMAND=%%~fN"
)

if defined NPM_COMMAND (
  call "%NPM_COMMAND%" %*
  exit /b %errorlevel%
)

echo Node.js/npm tidak ditemukan. Pasang Node.js lalu buka ulang terminal.
exit /b 9009
