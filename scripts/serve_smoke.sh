#!/usr/bin/env bash
# Live-стенд для dogfooding: Google Chat -> ngrok -> localhost:8000 -> app.
#
# Usage:
#   scripts/serve_smoke.sh https://xxxx.ngrok-free.app [app.module:app]
#   CHATTICE_AUDIENCE=https://xxxx.ngrok-free.app scripts/serve_smoke.sh
#
# App по умолчанию — examples.smoke_http:app; для Stage A стенда:
#   scripts/serve_smoke.sh https://xxxx.ngrok-free.app examples.live_http:app
#
# Убивает прошлый слушатель :8000, поднимает uvicorn с PYTHONPATH=src
# (uv run --extra иногда ломает editable-install — поэтому PYTHONPATH).

set -euo pipefail

NGROK_URL="${1:-${CHATTICE_AUDIENCE:-}}"
if [[ -z "$NGROK_URL" ]]; then
    echo "usage: serve_smoke.sh <ngrok-https-url> [app.module:app]" >&2
    exit 1
fi

APP="${2:-examples.smoke_http:app}"

cd "$(dirname "$0")/.."

if lsof -ti tcp:8000 >/dev/null 2>&1; then
    echo "[serve] killing stale listener on :8000"
    lsof -ti tcp:8000 | xargs kill -9
    sleep 1
fi

export PYTHONPATH=src
export CHATTICE_AUDIENCE="$NGROK_URL"

exec uv run --extra fastapi uvicorn "$APP" \
    --host 0.0.0.0 --port 8000
