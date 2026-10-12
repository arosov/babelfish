"""Track B launcher: run the stock babelfish pipeline with Redux (int4) weights.

Throwaway experiment companion to scripts/run.bat (plan:
~/.opencode/plan/parakeet-redux-prototypes.md, Track B). Behavior is
identical to `run.bat` — live microphone, Ghost updates on the terminal,
`--type` typing into the focused app, hotkeys, everything — except what
sits behind engine.transcribe(): the Parakeet Redux ONNX export instead of
the fp32 v3 weights.

Mechanics:
  1. Swap the shared-cache weights dir `nemo-parakeet-tdt-0.6b-v3` for the
     staged export (`models/nemo-parakeet-tdt-0.6b-v3-redux-export`),
     parking the fp32 weights beside it (…-v3int8-baseline).
  2. Launch the exact run.bat chain (bootstrap.py -> babelfish CLI,
     passthrough args) in the foreground — same console, same DLL env.
  3. On exit (normal or Ctrl+C), restore the fp32 weights dir.

Standardlibrary only — runs under any Python 3.10+ (uv run --no-project).

Usage (via scripts/run_redux.bat):
  scripts/run_redux.bat                # live mic, CPU, terminal ghosts
  scripts/run_redux.bat --type         # also type Ghost/Final into apps
  scripts/run_redux.bat --wakeword hey_jarvis   # any babelfish flag passes through
  scripts/run_redux.bat --restore-only # undo a stuck swap and exit

NOTE: `--cpu` is always prepended (this is the Redux-on-CPU track) unless
REDUX_ALLOW_GPU=1 is set in the environment.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# UTF-8 console I/O (emoji logs vs Windows charmap codecs — same guard as
# main.py).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

REPO = Path(__file__).resolve().parent.parent
ACTIVE_NAME = "nemo-parakeet-tdt-0.6b-v3"
PARKED_NAME = "nemo-parakeet-tdt-0.6b-v3-v3int8-baseline"
EXPORT_SUBDIR = "models/nemo-parakeet-tdt-0.6b-v3-redux-export"
EXPORT_FILES = (
    "config.json",
    "vocab.txt",
    "encoder-model.onnx",
    "decoder_joint-model.onnx",
)
REDUX_CONFIG_MARKER = "ternary_weights"


def resolve_uv() -> str:
    candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "VogonPoet/Cache/bin/uv.exe"
    if candidate.exists():
        return str(candidate)
    import shutil

    uv = shutil.which("uv")
    if not uv:
        print("error: uv not found (see scripts/run.bat for the resolution rules)")
        sys.exit(1)
    return uv


def cache_models_dir() -> Path:
    """Mirror the engine's resolution: config cache.cache_dir, then
    VOGON_APP_CACHE_DIR, then repo-local models/. The first candidate that
    CONTAINS the active dir wins."""
    config = REPO / "babelfish.config.json"
    candidates = []
    if config.exists():
        import json

        try:
            cache_dir = json.loads(config.read_text(encoding="utf-8")).get("cache", {}).get("cache_dir")
            if cache_dir:
                candidates.append(Path(cache_dir) / "models")
        except Exception:
            pass
    env_cache = os.environ.get("VOGON_APP_CACHE_DIR")
    if env_cache:
        candidates.append(Path(env_cache) / "models")
    candidates.append(REPO / "models")
    for candidate in candidates:
        if (candidate / ACTIVE_NAME).exists() or (candidate / PARKED_NAME).exists():
            return candidate
    print("error: no parakeet weights dir found in any candidate location")
    sys.exit(1)


def is_redux(models: Path) -> bool:
    import json

    cfg = models / ACTIVE_NAME / "config.json"
    if not cfg.exists():
        return False
    try:
        return REDUX_CONFIG_MARKER in cfg.read_text(encoding="utf-8")
    except Exception:
        return False


def swap(models: Path) -> None:
    active = models / ACTIVE_NAME
    parked = models / PARKED_NAME
    export = REPO / EXPORT_SUBDIR
    missing = [f for f in EXPORT_FILES if not (export / f).exists()]
    if missing:
        print(f"error: Redux export missing files in {export}: {missing}")
        print("       re-download first (hf download eschmidbauer/parakeet-redux-onnx ...)")
        sys.exit(1)
    if active.exists() and not is_redux(models):
        if parked.exists():
            print(
                f"error: both fp32 active ({active}) and parked ({parked}) exist — "
                "ambiguous state. Fix manually or run with --restore-only."
            )
            sys.exit(1)
        parked.parent.mkdir(parents=True, exist_ok=True)
        active.rename(parked)
        print(f"🔄 Parked fp32 weights: {parked}")
    active.mkdir(parents=True, exist_ok=True)
    for fname in EXPORT_FILES:
        src = export / fname
        dst = active / fname
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
    print(f"🧠 Redux (int4) weights active in: {active}")


def restore(models: Path) -> None:
    active = models / ACTIVE_NAME
    parked = models / PARKED_NAME
    if is_redux(models):
        shutil.rmtree(active, ignore_errors=True)
        print(f"🧹 Removed Redux weights: {active}")
    if parked.exists():
        parked.rename(active)
        print(f"✅ Restored fp32 weights: {active}")


def main() -> None:
    args = sys.argv[1:]
    restore_only = "--restore-only" in args
    passthrough = [a for a in args if a != "--restore-only"]

    uv = resolve_uv()
    models = cache_models_dir()
    print(f"🎯 Weights location (shared cache): {models}")

    if restore_only:
        restore(models)
        return

    # Track B is Redux via ORT on the CPU: force --cpu in memory for this
    # run (REDUX_ALLOW_GPU=1 escapes the guard).
    if "cpu" not in passthrough and os.environ.get("REDUX_ALLOW_GPU") != "1":
        passthrough = ["--cpu", *passthrough]
        print("➕ Prepended --cpu (Redux-on-CPU track; REDUX_ALLOW_GPU=1 to skip)")

    # Env seeding mirroring run.bat, so the bootstrap chain resolves the
    # same uv caches and artifacts.
    env = os.environ.copy()
    env.setdefault("VOGON_APP_CACHE_DIR", "F:\\vogonpoet_cache")
    env.setdefault("UV_CACHE_DIR", os.path.join(env["VOGON_APP_CACHE_DIR"], "uv"))
    env.setdefault("UV_PYTHON_INSTALL_DIR", os.path.join(env["VOGON_APP_CACHE_DIR"], "uv", "python"))
    env.setdefault("UV_CMD", uv)

    swapped_fresh = not is_redux(models)
    swap(models)  # idempotent: handles crash leftovers by reusing the active dir
    try:
        cmd = [uv, "run", "--no-project", "--python", "3.12.8", str(REPO / "scripts/bootstrap.py"), *passthrough]
        print(f"🚀 Launching babelfish (passthrough: {passthrough})")
        ret = subprocess.call(cmd, env=env, cwd=str(REPO))
        print(f"🛑 babelfish exited with code {ret}")
    except KeyboardInterrupt:
        print("\n🛑 Interrupted — restoring weights before exit")
        ret = 130
    finally:
        if swapped_fresh:
            restore(models)
        else:
            print(
                "ℹ️ Weights were ALREADY redux-swapped (crash leftover); leaving them "
                "in place. Run `scripts/run_redux.py --restore-only` to restore fp32."
            )


if __name__ == "__main__":
    main()
