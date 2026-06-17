#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_URL="http://127.0.0.1:5173"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '[gs3d-dev] %s\n' "$1"
}

fail() {
  printf '[gs3d-dev] ERROR: %s\n' "$1" >&2
  exit 1
}

node_major() {
  local node_bin="$1"
  "$node_bin" -p "Number(process.versions.node.split('.')[0])" 2>/dev/null || printf '0\n'
}

find_node_dir() {
  local candidates=()
  if [[ -n "${NODE_BIN_DIR:-}" ]]; then
    candidates+=("$NODE_BIN_DIR")
  fi
  candidates+=(
    "$HOME/.nvm/versions/node/v20.19.6/bin"
  )
  if command -v node >/dev/null 2>&1; then
    candidates+=("$(dirname "$(command -v node)")")
  fi

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ ! -x "$candidate/node" || ! -x "$candidate/npm" ]]; then
      continue
    fi
    if (( "$(node_major "$candidate/node")" >= 18 )); then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

cleanup() {
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || fail "Python venv not found. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
[[ -d "$ROOT_DIR/frontend/node_modules" ]] || fail "Frontend dependencies not found. Run: PATH=/home/jialiang/.nvm/versions/node/v20.19.6/bin:\$PATH npm --prefix frontend install"

NODE_DIR="$(find_node_dir)" || fail "Node.js 18+ not found. Set NODE_BIN_DIR to a Node 18+ bin directory."
log "Using Node: $("$NODE_DIR/node" -v)"
log "Starting backend: ${BACKEND_URL}"
"$PYTHON_BIN" "$ROOT_DIR/RT_tool.py" &
BACKEND_PID="$!"

log "Starting frontend: ${FRONTEND_URL}"
(
  cd "$ROOT_DIR/frontend"
  PATH="$NODE_DIR:$PATH" npm run dev
) &
FRONTEND_PID="$!"

log "Open ${FRONTEND_URL}"
log "Backend API is proxied to ${BACKEND_URL}"
wait -n "$BACKEND_PID" "$FRONTEND_PID"
