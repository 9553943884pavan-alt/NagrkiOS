@echo off
setlocal
set NAGRIKOS_MODE=demo
cd /d "%~dp0..\backend"
if not exist ".venv\Scripts\python.exe" (
  echo [NagrikOS] Creating a Python environment...
  py -3 -m venv .venv || goto :error
)
echo [NagrikOS] Installing / verifying backend dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
echo [NagrikOS] Backend and no-install UI: http://127.0.0.1:8000
echo [NagrikOS] API docs: http://127.0.0.1:8000/docs
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
exit /b %errorlevel%
:error
echo [NagrikOS] Could not start. Check Python installation and internet access for first-time pip install.
pause
exit /b 1
