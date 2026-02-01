#!/bin/sh
set -e

# Create local .contextbuilder directory for auth symlinks
mkdir -p /app/.contextbuilder

# If Azure Files mount has auth files, symlink them so they persist across restarts
AUTH_DIR="${WORKSPACE_PATH:-.}/.auth"
if [ -d "$AUTH_DIR" ]; then
    for f in users.json sessions.json; do
        if [ -f "$AUTH_DIR/$f" ]; then
            ln -sf "$AUTH_DIR/$f" /app/.contextbuilder/"$f"
            echo "[entrypoint] Linked $f from $AUTH_DIR"
        fi
    done
fi

exec uvicorn context_builder.api.main:app --host 0.0.0.0 --port 8000
