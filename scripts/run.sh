#!/usr/bin/env bash
# Babelfish standalone launcher (Linux/macOS).
#
# Uv resolution mirrors the VogonPoet app (UvExecutor):
#   1. the app cache bin dir (XDG_CACHE_HOME/vogonpoet/bin or
#      ~/.cache/vogonpoet/bin) -- mirrors SettingsRepository.appCacheDir.
#      NOTE: VogonPoet's uv-downloader currently only fetches the Windows
#      binary (uv.exe), so on Linux this dir is normally empty and the
#      system `uv` on PATH is the realistic source.
#   2. plain `uv` on PATH
VPOET_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/vogonpoet"
if [ -x "$VPOET_CACHE/bin/uv" ]; then
    BABELFISH_UV="$VPOET_CACHE/bin/uv"
elif command -v uv >/dev/null 2>&1; then
    BABELFISH_UV="uv"
else
    echo "error: uv not found. Install uv (https://docs.astral.sh/uv/getting-started/)" >&2
    exit 1
fi

# --- Shared model cache: reuse VogonPoet's Parakeet install ---
# Falls back to onnx-asr's HF cache (auto-download on first run) otherwise.
if [ -z "${VOGON_APP_CACHE_DIR}" ]; then
    # TODO: set this to this machine's VogonPoet cache directory
    # (the dir containing models/nemo-parakeet-tdt-0.6b-v3).
    VOGON_APP_CACHE_DIR="/TODO/set/your/vogonpoet_cache"
    export VOGON_APP_CACHE_DIR
fi

# Point uv's package/python caches at the shared cache as well, matching
# UvExecutor, so a uv from either source reuses the same artifacts.
export UV_CACHE_DIR="${UV_CACHE_DIR:-${VOGON_APP_CACHE_DIR}/uv}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-${VOGON_APP_CACHE_DIR}/uv/python}"

# The bootstrap re-invokes this same uv for sync + the final CLI launch.
export UV_CMD="${UV_CMD:-$BABELFISH_UV}"

# Delegate to babelfish's own bootstrap (ADR 0006): hardware detection,
# ORT-flavor sync with self-heal, model provisioning, DLL-path injection,
# then the babelfish CLI. All args pass through to the CLI
# (e.g. ./run.sh --wakeword hey_jarvis --cpu --type --server)
exec "$BABELFISH_UV" run --no-project --python 3.12.8 "$(cd "$(dirname "$0")" && pwd)/bootstrap.py" "$@"
