@echo off
rem ===========================================================================
rem  NewMathAgent one-click launcher: start the web driver + open the panel.
rem  Double-click this file. The real work lives in runtime\launch.py (docstring
rem  there explains why the logic is not in this file).
rem
rem  Name is run.bat, not start.bat: `start` is a cmd builtin, so typing `start`
rem  in this folder would run something else entirely.
rem
rem  ASCII only on purpose: cmd.exe reads .bat in the OEM codepage (936 here), so
rem  non-ASCII in this file mojibakes or breaks parsing on some machines. All the
rem  Chinese a human sees comes from launch.py, which reconfigures stdout to
rem  UTF-8 (the `chcp 65001` below makes that render).
rem
rem  Why a .bat when there is already run.ps1: .ps1 is blocked unless PowerShell's
rem  execution policy allows it -- this machine is 'Restricted', so run.ps1 needs
rem  -ExecutionPolicy Bypass every time. A .bat needs no policy, so a double-click
rem  always works (also on a fresh machine you just copied the folder onto).
rem ===========================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "LAUNCH=runtime\launch.py"
if not exist "%LAUNCH%" (
  echo [x] Missing %LAUNCH% -- copy the whole project folder, not just part of it.
  pause
  exit /b 2
)

rem Only *a* Python is needed here: launch.py re-execs itself with the project's
rem own interpreter from config\runtime.local.json. Try the py launcher, then PATH.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%LAUNCH%" %*
  goto :finished
)
where python >nul 2>nul
if not errorlevel 1 (
  python "%LAUNCH%" %*
  goto :finished
)

echo.
echo [x] No Python found (tried: py -3, python).
echo     Install Python 3.11+ or create the project venv, then put its path in
echo     config\runtime.local.json -- see docs/ENVIRONMENT.md.
echo.
pause
exit /b 3

:finished
rem Keep this window open only when something went wrong, so the reason stays
rem readable; on success the browser is already open and this window may close.
if errorlevel 1 (
  echo.
  pause
)
endlocal
