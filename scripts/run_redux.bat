@echo off
rem Track B launcher: babelfish with Redux (int4) weights, run.bat semantics.
rem
rem Same uv resolution and env seeding as scripts/run.bat; delegates to
rem scripts/run_redux.py which swaps the shared-cache weights, launches the
rem bootstrap chain in the foreground (live mic, terminal Ghost updates,
rem hotkeys; pass --type to type into the focused app), and restores the
rem fp32 weights on exit.
rem
rem   scripts\run_redux.bat                       (live mic, CPU)
rem   scripts\run_redux.bat --type                (also type into apps)
rem   scripts\run_redux.bat --wakeword hey_jarvis (any CLI flag passes through)
rem   scripts\run_redux.bat --restore-only        (undo a stuck swap)

set "BABELFISH_UV=uv"
if exist "%LOCALAPPDATA%\VogonPoet\Cache\bin\uv.exe" (
    set "BABELFISH_UV=%LOCALAPPDATA%\VogonPoet\Cache\bin\uv.exe"
)

if "%VOGON_APP_CACHE_DIR%"=="" (
    set VOGON_APP_CACHE_DIR=F:\vogonpoet_cache
)
if not defined UV_CACHE_DIR set "UV_CACHE_DIR=%VOGON_APP_CACHE_DIR%\uv"
if not defined UV_PYTHON_INSTALL_DIR set "UV_PYTHON_INSTALL_DIR=%VOGON_APP_CACHE_DIR%\uv\python"
if not defined UV_CMD set "UV_CMD=%BABELFISH_UV%"

"%BABELFISH_UV%" run --no-project --python 3.12.8 "%~dp0run_redux.py" %*
