#!/bin/bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/export/server/project/sales_panorama_dashboard}"
PID_DIR="$APP_ROOT/output/pids"

stop_pid_file() {
  name="$1"
  file="$PID_DIR/$name.pid"
  if [ ! -f "$file" ]; then
    echo "INFO: $name pid file not found"
    return
  fi

  pid="$(cat "$file")"
  if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid"
    echo "OK: stopped $name pid $pid"
  else
    echo "INFO: $name pid $pid is not running"
  fi
  rm -f "$file"
}

stop_pid_file backend
stop_pid_file frontend
