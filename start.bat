@echo off
REM ============================================================
REM Fridge Chat Credits – start (Windows)
REM Leave this window open while you stream.
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Chat Credits is not installed yet.
  echo.
  echo Double-click  install.bat  in this folder once.
  echo Or from the workshop folder:  INSTALL Chat Credits.bat
  echo.
  pause
  exit /b 1
)

if not exist "config\config.yaml" (
  if exist "config\config.example.yaml" (
    copy /Y "config\config.example.yaml" "config\config.yaml" >nul
  )
)

echo.
echo Starting Fridge Chat Credits...
echo.
echo   Control desk:  http://127.0.0.1:3854/
echo   Overlay:       http://127.0.0.1:3854/overlay/credits.html
echo.
echo Leave this window open while you stream. Press Ctrl+C to stop.
echo.

".venv\Scripts\python.exe" main.py
set EXITCODE=%ERRORLEVEL%

echo.
if not %EXITCODE%==0 (
  echo Chat Credits exited with code %EXITCODE%.
  echo If you see a missing package error, run install.bat again.
) else (
  echo Chat Credits stopped.
)
echo.
pause
endlocal
exit /b %EXITCODE%
