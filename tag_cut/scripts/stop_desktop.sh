#!/usr/bin/env bash
# Stop all tag_cut desktop-related processes (Vite / Electron / API).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VITE_PORT="${TAG_CUT_VITE_PORT:-5173}"
API_PORT="${TAG_CUT_API_PORT:-8765}"

log() { echo "[tag_cut:stop] $*"; }

kill_port() {
  local port="$1"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    log "port $port: free"
    return 0
  fi
  for pid in $pids; do
    local cmd
    cmd="$(ps -p "$pid" -o comm= 2>/dev/null || echo '?')"
    log "port $port: SIGTERM pid=$pid ($cmd)"
    kill "$pid" 2>/dev/null || true
  done
  sleep 0.4
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    for pid in $pids; do
      log "port $port: SIGKILL pid=$pid"
      kill -9 "$pid" 2>/dev/null || true
    done
    sleep 0.2
  fi
}

# Electron / concurrently leftovers whose command line mentions this app path
kill_matching() {
  local pattern="$1"
  local pids
  # macOS ps: -ax -o pid=,command=
  pids="$(ps -ax -o pid= -o command= 2>/dev/null | grep -F "$pattern" | grep -v grep | awk '{print $1}' || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi
  for pid in $pids; do
    log "match '$pattern': SIGTERM pid=$pid"
    kill "$pid" 2>/dev/null || true
  done
  sleep 0.3
  pids="$(ps -ax -o pid= -o command= 2>/dev/null | grep -F "$pattern" | grep -v grep | awk '{print $1}' || true)"
  for pid in $pids; do
    log "match '$pattern': SIGKILL pid=$pid"
    kill -9 "$pid" 2>/dev/null || true
  done
}

log "root=$ROOT"
kill_port "$VITE_PORT"
kill_port "$API_PORT"
kill_matching "$ROOT/apps/desktop"
kill_matching "tag_cut/apps/desktop"
# stale wait-on / concurrently from previous electron:dev
kill_matching "wait-on http://127.0.0.1:${VITE_PORT}"

log "done"
