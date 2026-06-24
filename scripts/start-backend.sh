#!/usr/bin/env bash
# Start the FastAPI backend (required for "Run Inspection" in the Next.js UI).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

if [[ -x "$ROOT/.venv/bin/uvicorn" ]]; then
  PY="$ROOT/.venv/bin/uvicorn"
elif command -v uvicorn >/dev/null 2>&1; then
  PY="uvicorn"
else
  echo "uvicorn not found. Run: pip install -r backend/requirements.txt"
  exit 1
fi

echo "Starting SiteCheck API on http://127.0.0.1:8000"
exec "$PY" main:app --reload --host 127.0.0.1 --port 8000
