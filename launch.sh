#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
API_HOST="${API_HOST:-127.0.0.1}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"

if [[ ! -x "$ROOT_DIR/.env/bin/uvicorn" ]]; then
  echo "Missing $ROOT_DIR/.env/bin/uvicorn"
  echo "Create/activate the Python environment and install dependencies first."
  exit 1
fi

if [[ ! -d "$ROOT_DIR/apps/web/node_modules" ]]; then
  echo "Missing $ROOT_DIR/apps/web/node_modules"
  echo "Run npm install in apps/web first."
  exit 1
fi

if [[ ! -x "$ROOT_DIR/apps/web/node_modules/.bin/vite" ]]; then
  echo "Missing $ROOT_DIR/apps/web/node_modules/.bin/vite"
  echo "Run npm install in apps/web first."
  exit 1
fi

clear_port() {
  local port="$1"
  local label="$2"
  local allowed_pattern="$3"
  local pids

  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return
  fi

  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue

    local command
    command="$(ps -p "$pid" -o command= 2>/dev/null || true)"

    if [[ "$command" =~ $allowed_pattern ]]; then
      echo "$label port $port is already used by a Quantapy dev process; stopping PID $pid."
      kill "$pid" 2>/dev/null || true
    else
      echo "$label port $port is already in use by PID $pid:"
      echo "  $command"
      echo "Stop that process or run with a different ${label^^}_PORT."
      exit 1
    fi
  done <<< "$pids"

  sleep 1

  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "$label port $port is still in use after cleanup."
    exit 1
  fi
}

clear_port "$API_PORT" "API" "uvicorn.*apps\.api\.quantapy_api\.main:app"
clear_port "$WEB_PORT" "WEB" "apps/web/node_modules/.bin/vite|apps/web/node_modules/vite|quantapy-workbench.*vite"

cleanup() {
  echo
  echo "Stopping Quantapy services..."
  if [[ -n "${API_PID:-}" ]]; then
    kill "$API_PID" 2>/dev/null || true
  fi
  if [[ -n "${WEB_PID:-}" ]]; then
    kill "$WEB_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Starting Quantapy API at http://$API_HOST:$API_PORT"
cd "$ROOT_DIR"
"$ROOT_DIR/.env/bin/uvicorn" apps.api.quantapy_api.main:app \
  --reload \
  --host "$API_HOST" \
  --port "$API_PORT" &
API_PID=$!

echo "Starting Quantapy Workbench at http://$WEB_HOST:$WEB_PORT"
cd "$ROOT_DIR/apps/web"
VITE_API_BASE="http://$API_HOST:$API_PORT" "$ROOT_DIR/apps/web/node_modules/.bin/vite" \
  --host "$WEB_HOST" \
  --port "$WEB_PORT" \
  --strictPort &
WEB_PID=$!

echo
echo "Quantapy is launching:"
echo "  API:      http://$API_HOST:$API_PORT"
echo "  Workbench: http://$WEB_HOST:$WEB_PORT"
echo
echo "Press Ctrl+C to stop both services."

wait "$API_PID" "$WEB_PID"
