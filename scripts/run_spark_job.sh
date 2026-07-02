#!/bin/bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/export/server/project/sales_panorama_dashboard}"
SPARK_HOME="${SPARK_HOME:-/export/server/spark}"
MASTER_URL="${MASTER_URL:-spark://node1:7077}"
export SPARK_RESULT_DIR="${SPARK_RESULT_DIR:-$APP_ROOT/output/spark_result}"

mkdir -p "$SPARK_RESULT_DIR"
cd "$APP_ROOT"

if [ ! -x "$SPARK_HOME/bin/spark-submit" ]; then
  echo "FAIL: spark-submit not found at $SPARK_HOME/bin/spark-submit"
  exit 1
fi

if ! command -v java >/dev/null 2>&1; then
  echo "FAIL: java command not found"
  exit 1
fi

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

JDBC_JAR_PATH="$(find_jdbc_jar || true)"
if [ -z "$JDBC_JAR_PATH" ] || [ ! -f "$JDBC_JAR_PATH" ]; then
  cat <<EOF
FAIL: SQL Server JDBC driver jar not found.

Spark needs the Microsoft SQL Server JDBC driver before it can read AdventureWorksDW.
Put the driver jar in one of these locations:
  $SPARK_HOME/jars/mssql-jdbc.jar
  $APP_ROOT/lib/mssql-jdbc.jar

Or run this script with an explicit path:
  JDBC_JAR=/path/to/mssql-jdbc-12.8.1.jre8.jar bash scripts/run_spark_job.sh

Your previous error was caused by this missing file:
  /export/server/spark/jars/mssql-jdbc.jar
EOF
  exit 2
fi

echo "Using SQL Server JDBC driver: $JDBC_JAR_PATH"
echo "Submitting EnterpriseSalesPanoramaSpark to $MASTER_URL"
"$SPARK_HOME/bin/spark-submit" \
  --master "$MASTER_URL" \
  --name EnterpriseSalesPanoramaSpark \
  --jars "$JDBC_JAR_PATH" \
  backend/spark_jobs/sales_spark_job.py

for file in kpis.json trend.json top_products.json channels.json geo_sales.json alerts.json; do
  if [ ! -s "$SPARK_RESULT_DIR/$file" ]; then
    echo "FAIL: missing Spark output $SPARK_RESULT_DIR/$file"
    exit 3
  fi
done

echo "OK: Spark results written to $SPARK_RESULT_DIR"
