#!/bin/bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/export/server/project/sales_panorama_dashboard}"
SPARK_HOME="${SPARK_HOME:-/export/server/spark}"
MASTER_HOST="${MASTER_HOST:-node1}"
MASTER_URL="${MASTER_URL:-spark://node1:7077}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-8088}"
RUN_SPARK_JOB="${RUN_SPARK_JOB:-1}"
RUN_AI_REPORT="${RUN_AI_REPORT:-1}"
START_SERVERS="${START_SERVERS:-1}"
AUTO_INSTALL_DEPS="${AUTO_INSTALL_DEPS:-1}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export SPARK_RESULT_DIR="${SPARK_RESULT_DIR:-$APP_ROOT/output/spark_result}"

LOG_DIR="$APP_ROOT/output/logs"
PID_DIR="$APP_ROOT/output/pids"
VENV_DIR="${VENV_DIR:-$APP_ROOT/.venv}"

fail() {
  echo "FAIL: $*"
  exit 1
}

ok() {
  echo "OK: $*"
}

warn() {
  echo "WARN: $*"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 command not found"
  ok "$1 command found"
}

check_port_free() {
  port="$1"
  label="$2"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn "( sport = :$port )" | grep -q ":$port"; then
      fail "$label port $port is already in use"
    fi
  elif command -v netstat >/dev/null 2>&1; then
    if netstat -ltn | awk '{print $4}' | grep -Eq "[:.]$port$"; then
      fail "$label port $port is already in use"
    fi
  else
    warn "ss/netstat not found, skip $label port check"
  fi
  ok "$label port $port available"
}

find_jdbc_jar() {
  if [ -n "${JDBC_JAR:-}" ]; then
    echo "$JDBC_JAR"
    return
  fi

  for pattern in \
    "$SPARK_HOME"/jars/mssql-jdbc*.jar \
    "$SPARK_HOME"/jars/sqljdbc*.jar \
    "$APP_ROOT"/lib/mssql-jdbc*.jar \
    "$APP_ROOT"/jars/mssql-jdbc*.jar
  do
    for candidate in $pattern; do
      if [ -f "$candidate" ]; then
        echo "$candidate"
        return
      fi
    done
  done
}

check_python_module() {
  "$PYTHON_BIN" - "$1" <<'PY'
import importlib
import sys
module = sys.argv[1]
importlib.import_module(module)
PY
}

install_python_deps() {
  if [ "${AUTO_INSTALL_DEPS}" != "1" ]; then
    fail "missing Python dependencies. Install with: $PYTHON_BIN -m pip install -i $PIP_INDEX_URL -r backend/requirements.txt"
  fi

  echo "Installing Python dependencies from backend/requirements.txt"
  "$PYTHON_BIN" -m pip install -i "$PIP_INDEX_URL" -r backend/requirements.txt || {
    cat <<EOF
FAIL: Python dependency installation failed.

Try manually:
  $PYTHON_BIN -m pip install -i $PIP_INDEX_URL -r backend/requirements.txt
EOF
    exit 1
  }
}

check_python_deps() {
  missing=""
  for module in fastapi uvicorn requests; do
    if check_python_module "$module"; then
      ok "Python module available: $module"
    else
      warn "Python module missing: $module"
      missing="1"
    fi
  done

  if [ -n "$missing" ]; then
    install_python_deps
    for module in fastapi uvicorn requests; do
      check_python_module "$module" || fail "Python module still missing after install: $module"
    done
  fi
  ok "required Python modules available"
}

cd "$APP_ROOT" || fail "project directory not found: $APP_ROOT"
mkdir -p "$SPARK_RESULT_DIR" "$LOG_DIR" "$PID_DIR"

echo "== 1. Basic environment =="
need_cmd java
need_cmd jps

if [ ! -x "$SPARK_HOME/bin/spark-submit" ]; then
  fail "spark-submit not found: $SPARK_HOME/bin/spark-submit"
fi
ok "spark-submit found at $SPARK_HOME/bin/spark-submit"

SYSTEM_PYTHON="${PYTHON_BIN:-$(command -v python3 || command -v python || true)}"
[ -n "$SYSTEM_PYTHON" ] || fail "python3/python command not found"
ok "system python found at $SYSTEM_PYTHON"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "Creating isolated Python venv at $VENV_DIR"
  "$SYSTEM_PYTHON" -m venv "$VENV_DIR" || fail "failed to create Python venv. Try: $SYSTEM_PYTHON -m pip install virtualenv"
fi
PYTHON_BIN="$VENV_DIR/bin/python"
ok "project python found at $PYTHON_BIN"

[ -f "$APP_ROOT/backend/app.py" ] || fail "backend/app.py not found"
[ -f "$APP_ROOT/frontend/index.html" ] || fail "frontend/index.html not found"
[ -f "$APP_ROOT/backend/spark_jobs/sales_spark_job.py" ] || fail "Spark job file not found"
ok "project files found"

JDBC_JAR_PATH="$(find_jdbc_jar || true)"
if [ -z "$JDBC_JAR_PATH" ] || [ ! -f "$JDBC_JAR_PATH" ]; then
  cat <<EOF
FAIL: SQL Server JDBC driver jar not found.

Fix:
  1. Put mssql-jdbc jar under:
     $SPARK_HOME/jars/mssql-jdbc.jar
     or $APP_ROOT/lib/mssql-jdbc.jar

  2. Or specify it manually:
     JDBC_JAR=/path/to/mssql-jdbc-12.8.1.jre8.jar bash scripts/start.sh

This is the same root cause as:
  java.io.FileNotFoundException: Jar /export/server/spark/jars/mssql-jdbc.jar not found
EOF
  exit 2
fi
export JDBC_JAR="$JDBC_JAR_PATH"
ok "SQL Server JDBC driver found: $JDBC_JAR"

echo "== 2. Python dependencies =="
check_python_deps

echo "== 3. Spark cluster =="
if command -v nc >/dev/null 2>&1; then
  if nc -z "$MASTER_HOST" 7077; then
    ok "Spark master reachable at $MASTER_HOST:7077"
  else
    warn "Spark master is not reachable at $MASTER_HOST:7077"
    if [ -x "$SPARK_HOME/sbin/start-all.sh" ]; then
      echo "Starting Spark cluster with $SPARK_HOME/sbin/start-all.sh"
      "$SPARK_HOME/sbin/start-all.sh"
      sleep 3
      nc -z "$MASTER_HOST" 7077 || fail "Spark master still unreachable after start-all.sh"
      ok "Spark master reachable after startup"
    else
      fail "cannot start Spark cluster because $SPARK_HOME/sbin/start-all.sh is missing"
    fi
  fi
else
  warn "nc not found, skip Spark master port check"
fi

if [ "${RUN_SPARK_JOB}" = "1" ]; then
  echo "== 4. Run Spark job =="
  bash scripts/run_spark_job.sh 2>&1 | tee "$SPARK_RESULT_DIR/spark_run.log"
else
  warn "skip Spark job because RUN_SPARK_JOB=$RUN_SPARK_JOB"
fi

echo "== 5. Validate Spark outputs =="
for file in kpis.json trend.json top_products.json channels.json geo_sales.json alerts.json; do
  [ -s "$SPARK_RESULT_DIR/$file" ] || fail "missing Spark output: $SPARK_RESULT_DIR/$file"
  ok "$file exists"
done

if [ "${RUN_AI_REPORT}" = "1" ]; then
  echo "== 6. Generate AI report =="
  if bash scripts/generate_ai_report.sh 2>&1 | tee "$SPARK_RESULT_DIR/ai_report_run.log"; then
    ok "AI report generated"
  else
    warn "AI report generation failed. Dashboard can still run with Spark JSON outputs."
  fi
else
  warn "skip AI report because RUN_AI_REPORT=$RUN_AI_REPORT"
fi

if [ "${START_SERVERS}" != "1" ]; then
  ok "environment check and data generation completed"
  exit 0
fi

echo "== 7. Start dashboard services =="
check_port_free "$BACKEND_PORT" "backend"
check_port_free "$FRONTEND_PORT" "frontend"

(
  cd "$APP_ROOT/backend"
  exec "$PYTHON_BIN" -m uvicorn app:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"
) >"$LOG_DIR/backend.log" 2>&1 &
echo $! > "$PID_DIR/backend.pid"
ok "backend started, pid $(cat "$PID_DIR/backend.pid"), log $LOG_DIR/backend.log"

(
  cd "$APP_ROOT/frontend"
  exec "$PYTHON_BIN" -m http.server "$FRONTEND_PORT" --bind "$FRONTEND_HOST"
) >"$LOG_DIR/frontend.log" 2>&1 &
echo $! > "$PID_DIR/frontend.pid"
ok "frontend started, pid $(cat "$PID_DIR/frontend.pid"), log $LOG_DIR/frontend.log"

echo
echo "Dashboard URL:"
echo "  http://$MASTER_HOST:$FRONTEND_PORT/index.html?v=20260630"
echo
echo "Stop services:"
echo "  bash scripts/stop.sh"
