#!/bin/bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/export/server/project/sales_panorama_dashboard}"
export SPARK_RESULT_DIR="${SPARK_RESULT_DIR:-$APP_ROOT/output/spark_result}"
export DEEPSEEK_MODEL="${DEEPSEEK_MODEL:-deepseek-v4-flash}"

cd "$APP_ROOT"

if [ ! -d "$SPARK_RESULT_DIR" ]; then
  echo "FAIL: Spark result directory does not exist: $SPARK_RESULT_DIR"
  exit 1
fi

python backend/ai/deepseek_v4_report.py
echo "OK: AI report generated at $SPARK_RESULT_DIR/ai_report.txt"
