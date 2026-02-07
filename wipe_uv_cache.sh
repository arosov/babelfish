#!/bin/bash
# Script to wipe all uv cache from the system

echo "🧹 Detecting uv cache directory..."
CACHE_DIR=$(uv cache dir)

if [ -z "$CACHE_DIR" ]; then
    echo "❌ Could not detect uv cache directory."
    exit 1
fi

echo "📂 Cache directory found: $CACHE_DIR"
echo "📊 Current cache size: $(uv cache size)"

echo "🗑️  Running official uv cache clean..."
uv cache clean

echo "✨ Cache cleaned successfully."
echo "📊 New cache size: $(uv cache size)"
