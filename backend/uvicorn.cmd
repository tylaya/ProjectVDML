@echo off
setlocal

set "PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Virtual environment tidak ditemukan. Buat .venv dan pasang backend\requirements.txt terlebih dahulu.
  exit /b 9009
)

"%PYTHON%" -m uvicorn %*
exit /b %errorlevel%
