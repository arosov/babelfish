@echo off
rem Babelfish standalone launcher (Windows).
rem
rem Uv resolution mirrors the VogonPoet app (UvExecutor):
rem   1. VogonPoet's app-managed binary in %LOCALAPPDATA%\VogonPoet\Cache\bin
rem   2. plain `uv` on PATH
set "BABELFISH_UV=uv"
if exist "%LOCALAPPDATA%\VogonPoet\Cache\bin\uv.exe" (
    set "BABELFISH_UV=%LOCALAPPDATA%\VogonPoet\Cache\bin\uv.exe"
)
where uv >nul 2>&1 || (
    if "%BABELFISH_UV%"=="uv" (
        echo error: uv not found. Install VogonPoet ^(which downloads uv.exe^)
        echo into %%LOCALAPPDATA%%\VogonPoet\Cache\bin, or install uv on your PATH.
        exit /b 1
    )
)

rem --- Shared model cache: reuse VogonPoet's Parakeet install ---
rem Falls back to onnx-asr's HF cache (auto-download on first run) otherwise.
if "%VOGON_APP_CACHE_DIR%"=="" (
    rem Per-machine fallback: the existing populated VogonPoet cache.
    set VOGON_APP_CACHE_DIR=F:\vogonpoet_cache
)

rem Point uv's package/python caches at the shared cache as well, matching
rem UvExecutor, so a uv from either source reuses the same artifacts.
if not defined UV_CACHE_DIR set "UV_CACHE_DIR=%VOGON_APP_CACHE_DIR%\uv"
if not defined UV_PYTHON_INSTALL_DIR set "UV_PYTHON_INSTALL_DIR=%VOGON_APP_CACHE_DIR%\uv\python"

rem All extra args are passed through to the babelfish CLI
rem (e.g. run.bat --wakeword hey_jarvis --cpu --type --server)
"%BABELFISH_UV%" run babelfish %*
