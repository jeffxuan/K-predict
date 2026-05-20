#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT/kronos_repo/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Kronos virtual environment is missing."
  echo "Run this first:"
  echo "  bash scripts/setup_workbench.sh"
  exit 1
fi

if [[ ! -d "$ROOT/app/node_modules" ]]; then
  echo "React dependencies are missing."
  echo "Run this first:"
  echo "  bash scripts/setup_workbench.sh"
  exit 1
fi

if [[ ! -f "$ROOT/data/prices.csv" || ! -d "$ROOT/data/kronos_daily" ]]; then
  echo "Demo data is missing; preparing it now."
  "$VENV_PY" "$ROOT/scripts/prepare_data.py" --no-live
fi

echo "Starting K-predict workbench API on http://127.0.0.1:7080"
echo "Starting React workbench on http://127.0.0.1:5173"
echo
echo "Keep this terminal open. Press Ctrl+C to stop both services."

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then kill "$API_PID" 2>/dev/null || true; fi
  if [[ -n "${APP_PID:-}" ]]; then kill "$APP_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

cd "$ROOT"
"$VENV_PY" -m workbench_api.app &
API_PID=$!

cd "$ROOT/app"
npm run dev &
APP_PID=$!

wait
