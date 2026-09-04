#!/usr/bin/env bash
# Bootstrap tag_cut on a fresh machine (macOS / Linux).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WITH_DESKTOP=0
WITH_MODELS=1
WITH_SKILL=0
for arg in "$@"; do
  case "$arg" in
    --with-desktop) WITH_DESKTOP=1 ;;
    --skip-models) WITH_MODELS=0 ;;
    --with-skill) WITH_SKILL=1 ;;
    -h|--help)
      echo "Usage: scripts/bootstrap.sh [--with-desktop] [--with-skill] [--skip-models]"
      exit 0
      ;;
  esac
done

echo "==> tag_cut root: $ROOT"

if ! command -v python3 >/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.11+ first." >&2
  exit 1
fi

PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "==> python3: $(command -v python3) ($PY_VER)"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' || {
  echo "ERROR: Need Python >= 3.11 (found $PY_VER)" >&2
  exit 1
}

if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  echo "WARN: ffmpeg/ffprobe missing. On macOS: brew install ffmpeg" >&2
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "==> creating .venv"
  python3 -m venv .venv
fi

echo "==> pip install -r requirements.txt"
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

mkdir -p data exports models input
[[ -f models/.gitkeep ]] || touch models/.gitkeep

if [[ "$WITH_MODELS" -eq 1 ]]; then
  echo "==> download recommended YOLO weights"
  PYTHONPATH=. .venv/bin/python scripts/tag_cut_cli.py models ensure || {
    echo "WARN: YOLO download failed (network?). You can retry later:" >&2
    echo "  PYTHONPATH=. .venv/bin/python scripts/tag_cut_cli.py models ensure" >&2
  }
fi

echo "==> env-check"
PYTHONPATH=. .venv/bin/python scripts/tag_cut_cli.py env-check

if [[ "$WITH_DESKTOP" -eq 1 ]]; then
  if ! command -v npm >/dev/null; then
    echo "ERROR: npm not found (needed for --with-desktop)" >&2
    exit 1
  fi
  echo "==> npm install (desktop)"
  (cd apps/desktop && npm install)
  echo "Desktop ready: cd apps/desktop && npm run electron:dev"
fi

if [[ "$WITH_SKILL" -eq 1 ]]; then
  echo "==> install agent skill (cursor/claude/codex)"
  PYTHONPATH=. .venv/bin/python scripts/install_agent_skill.py --targets all --force
fi

echo
echo "OK. Next:"
echo "  cd $ROOT"
echo "  PYTHONPATH=. .venv/bin/python scripts/tag_cut_cli.py analyze --batch ../input/<你的批次> --limit 1"
echo "Docs: docs/INSTALL.md  docs/AGENT_INSTALL.md"
