#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/home/musa/Desktop/asistant"
VENV_PY="$BASE_DIR/.venv/bin/python"
LOG_DIR="$BASE_DIR/logs"

mkdir -p "$LOG_DIR"

start_if_not_running() {
  local name="$1"
  local script="$2"
  local pidfile="$LOG_DIR/${name}.pid"
  if pgrep -f "$script" >/dev/null 2>&1; then
    return 0
  fi
  nohup "$VENV_PY" "$script" > "$LOG_DIR/${name}.log" 2>&1 &
  echo $! > "$pidfile"
}

start_if_not_running "bot" "$BASE_DIR/scripts/run_bot.py"
start_if_not_running "web" "$BASE_DIR/scripts/run_web.py"

sleep 1
xdg-open "http://localhost:8080" >/dev/null 2>&1 || true
