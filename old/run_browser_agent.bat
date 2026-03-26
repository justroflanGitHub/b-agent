@echo off
REM Browser Agent Host Runner for Windows
REM This runs the browser agent directly on the host system for visible browser operation

echo Starting Browser Agent on host system...
echo Browser will open and be visible on top of other applications
echo.

REM Set environment variables for host operation
set BROWSER_AGENT_MOCK_MODE=false
set BROWSER_HEADLESS=false
set LM_STUDIO_URL=http://127.0.0.1:1234

REM Run the simple browser agent API
python simple_browser_api.py

pause
