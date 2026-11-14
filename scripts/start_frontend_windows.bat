@echo off
setlocal
cd /d "%~dp0..\frontend"
where npm >nul 2>&1 || goto :missing
if not exist node_modules (
  echo [NagrikOS] Installing React frontend dependencies...
  call npm install || goto :error
)
echo [NagrikOS] Frontend URL: http://127.0.0.1:5173
echo [NagrikOS] Ensure backend on port 8000 is running in another terminal.
call npm run dev
exit /b %errorlevel%
:missing
echo [NagrikOS] Node.js / npm not installed. Use http://127.0.0.1:8000 instead.
pause
exit /b 1
:error
echo [NagrikOS] Install failed. Check network access. The backend's http://127.0.0.1:8000 UI still works.
pause
exit /b 1
