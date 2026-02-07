#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from pathlib import Path

def get_readme_summary(path):
    for name in ['README.md', 'readme.md', 'README.txt', 'readme.txt']:
        readme_path = path / name
        if readme_path.exists():
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if len(content) > 3000:
                        return content[:3000] + "\n\n... (README truncated for length) ..."
                    return content
            except Exception:
                return "Error reading README."
    return "No README found."

def get_codebase_summary(path):
    path = Path(path).resolve()
    if not path.exists():
        return f"## Codebase: {path.name} (NOT FOUND)\nPath: {path}"

    summary = [f"## Codebase: {path.name}"]
    summary.append(f"- **Path**: `{path}`")
    
    # 1. Structure Overview
    try:
        items = os.listdir(path)
        dirs = [i for i in items if (path / i).is_dir() and not i.startswith('.')]
        summary.append(f"- **Structure**: {', '.join(dirs[:15])}{'...' if len(dirs) > 15 else ''}")
    except Exception:
        pass

    # 2. Audio Pipeline Features (Improved scanning)
    keywords = ["pyaudio", "sounddevice", "vad", "stt", "transcribe", "microphone", "recorder", "stream", "nemo", "whisper", "soxr"]
    found_files = set()
    
    try:
        # Use find to get a broader list of relevant files
        cmd = f"find '{path}' -maxdepth 3 -name '*.py' | grep -iE '({'|'.join(keywords)})' | head -n 20"
        output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        for line in output.splitlines():
            if line.strip():
                found_files.add(Path(line).name)
    except Exception:
        pass

    if found_files:
        summary.append(f"- **Key Files (Audio/STT)**: {', '.join(list(found_files))}")

    # 3. README Content
    summary.append("\n### README Content")
    summary.append(get_readme_summary(path))

    return "\n".join(summary)

def main():
    # Progress indicator for the user
    print("🔍 [Hook] Preparing project landscape overviews...", file=sys.stderr)
    
    project_dir = os.environ.get("GEMINI_PROJECT_DIR", os.getcwd())
    settings_path = Path(project_dir) / ".gemini" / "settings.json"
    
    directories = [project_dir]
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                included = settings.get("context", {}).get("includeDirectories", [])
                directories.extend(included)
        except Exception:
            pass

    overviews = []
    for d in directories:
        d_path = Path(d)
        print(f"  - Indexing {d_path.name}...", file=sys.stderr)
        overviews.append(get_codebase_summary(d_path))

    # Construct the injected context with clear instructions for the LLM
    injected_text = (
        "IMPORTANT: The following is a TECHNICAL OVERVIEW of the current project and its linked codebases.\n"
        "I have performed a pre-scan of these directories to save time and tokens.\n"
        "USE THIS OVERVIEW to answer architectural and feature-related questions.\n"
        "ONLY use file-system tools (like list_directory or read_file) if you need to inspect specific implementation details NOT covered in the READMEs below.\n\n"
        "# Project Landscape Overviews\n\n"
    )
    injected_text += "\n\n---\n\n".join(overviews)
    injected_text += "\n\n---\n*Context provided by .gemini/hooks/codebase_overview.py*"

    # Final output to CLI
    print("✅ [Hook] Project landscape injected into session memory.", file=sys.stderr)
    print(json.dumps({
        "systemMessage": "🚀 Project landscape overviews for linked codebases have been loaded into context.",
        "hookSpecificOutput": {
            "additionalContext": injected_text
        }
    }))

if __name__ == "__main__":
    main()