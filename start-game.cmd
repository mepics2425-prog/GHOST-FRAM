@echo off
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed. Open index.html in Chrome or Edge instead.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:4173 in your browser.
echo Close this window or press Ctrl+C to stop the server.
node server.cjs
