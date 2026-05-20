#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KRONOS_DIR="$ROOT/kronos_repo"
VENV_DIR="$KRONOS_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "K-predict setup"
echo "Project: $ROOT"
echo

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    echo "Please install it and run this script again."
    exit 1
  fi
}

require_cmd git
require_cmd "$PYTHON_BIN"
require_cmd node
require_cmd npm

"$PYTHON_BIN" - <<'PY'
import sys
major, minor = sys.version_info[:2]
if major != 3 or minor < 9 or minor > 11:
    raise SystemExit(
        f"Python {major}.{minor} detected. Kronos is best installed with Python 3.9-3.11. "
        "Install a supported Python and rerun, or set PYTHON_BIN=/path/to/python."
    )
PY

NODE_MAJOR="$(node -p "process.versions.node.split('.')[0]")"
if [[ "$NODE_MAJOR" -lt 20 ]]; then
  echo "Node.js 20+ is required. Detected: $(node -v)"
  exit 1
fi

if [[ ! -d "$KRONOS_DIR/.git" ]]; then
  echo "Cloning Kronos into kronos_repo/ ..."
  git clone https://github.com/shiyu-coder/Kronos.git "$KRONOS_DIR"
else
  echo "Kronos repository already exists."
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Creating Python virtual environment in kronos_repo/.venv ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PY="$VENV_DIR/bin/python"
echo "Upgrading pip ..."
"$VENV_PY" -m pip install --upgrade pip

echo "Installing Kronos and workbench Python dependencies ..."
"$VENV_PY" -m pip install -r "$KRONOS_DIR/requirements.txt"
if [[ -f "$KRONOS_DIR/webui/requirements.txt" ]]; then
  "$VENV_PY" -m pip install -r "$KRONOS_DIR/webui/requirements.txt"
fi
"$VENV_PY" -m pip install pytest

echo "Installing React workbench dependencies ..."
cd "$ROOT/app"
npm install

echo "Preparing demo SCI/SIC data ..."
cd "$ROOT"
"$VENV_PY" scripts/prepare_data.py --no-live

echo
echo "Setup complete."
echo "Start the workbench with:"
echo "  bash scripts/start_workbench.sh"
echo
echo "Then open:"
echo "  http://127.0.0.1:5173"
echo
echo "Note: the first Kronos prediction may download model weights from Hugging Face."
