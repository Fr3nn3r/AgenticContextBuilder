#!/usr/bin/env bash
# Start the backend (uvicorn) dev server.
# Usage: ./scripts/start-backend.sh [port]
# Defaults to port based on worktree detection.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
DIR_NAME="$(basename "$REPO_DIR")"

# Port assignments per worktree
case "$DIR_NAME" in
    AgenticContextBuilder)     BACKEND_PORT=8000 ;;
    AgenticContextBuilder-wt1) BACKEND_PORT=8001 ;;
    AgenticContextBuilder-wt2) BACKEND_PORT=8002 ;;
    AgenticContextBuilder-wt3) BACKEND_PORT=8003 ;;
    *) echo "Unknown worktree: $DIR_NAME"; exit 1 ;;
esac

# Allow override via argument
PORT="${1:-$BACKEND_PORT}"

# Kill any existing process on the port
if lsof -ti:"$PORT" >/dev/null 2>&1; then
    echo "Killing existing process on port $PORT..."
    kill -9 $(lsof -ti:"$PORT") 2>/dev/null || true
    sleep 1
fi

echo "=== Backend Server ==="
echo "Worktree: $DIR_NAME"
echo "Port:     $PORT"
echo "URL:      http://localhost:$PORT"
echo "Press Ctrl+C to stop."
echo ""

cd "$REPO_DIR"

# Activate venv: prefer .venv-wsl (WSL-native), fall back to .venv
if [ -f ".venv-wsl/bin/activate" ]; then
    source .venv-wsl/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "No venv found. Run: uv venv .venv-wsl && uv pip install -e ."
    exit 1
fi

PYTHONPATH=src uvicorn context_builder.api.main:app \
    --reload \
    --host 0.0.0.0 \
    --port "$PORT" \
    --limit-concurrency 50 \
    --timeout-keep-alive 5
