#!/usr/bin/env bash
# One-click: stop stale tag_cut services, then start Electron desktop (Vite + API + UI).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DESKTOP="$ROOT/apps/desktop"
VITE_PORT="${TAG_CUT_VITE_PORT:-5173}"
API_PORT="${TAG_CUT_API_PORT:-8765}"

log() { echo "[tag_cut:start] $*"; }
die() { echo "[tag_cut:start] ERROR: $*" >&2; exit 1; }

cd "$ROOT"

log "stopping old services…"
bash "$ROOT/scripts/stop_desktop.sh"

if [[ ! -x "$ROOT/.venv/bin/python" && ! -x "$ROOT/.venv/bin/python3" ]]; then
  die "missing .venv — run: ./scripts/bootstrap.sh --with-desktop"
fi
if [[ ! -d "$DESKTOP/node_modules" ]]; then
  log "node_modules missing — running npm install"
  (cd "$DESKTOP" && npm install) || die "npm install failed"
fi
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  log "WARN: ffmpeg/ffprobe not on PATH (clip preview/export may fail)"
fi

# Final port check
for port in "$VITE_PORT" "$API_PORT"; do
  if lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    die "port $port still busy after stop — free it manually: lsof -tiTCP:$port -sTCP:LISTEN | xargs kill -9"
  fi
done

log "starting Electron (Vite :$VITE_PORT + API :$API_PORT)…"
log "cwd=$DESKTOP"
cd "$DESKTOP"
exec npm run electron:dev
