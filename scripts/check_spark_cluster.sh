#!/bin/bash
set -u

SPARK_HOME="${SPARK_HOME:-/export/server/spark}"
MASTER_HOST="${MASTER_HOST:-node1}"
MASTER_URL="${MASTER_URL:-spark://node1:7077}"
NODES="${NODES:-node1 node2 node3}"

status=0

check_cmd() {
  label="$1"
  shift
  if "$@" >/tmp/check_spark_cluster.out 2>&1; then
    echo "OK: $label"
  else
    echo "FAIL: $label"
    cat /tmp/check_spark_cluster.out
    status=1
  fi
}

echo "== Local runtime =="
check_cmd "java version" java -version
check_cmd "spark-submit version" "$SPARK_HOME/bin/spark-submit" --version
check_cmd "jps available" jps

echo "== Local Spark processes =="
jps

echo "== Master ports =="
if command -v nc >/dev/null 2>&1; then
  check_cmd "$MASTER_HOST:7077 reachable" nc -z "$MASTER_HOST" 7077
else
  echo "WARN: nc not found, skip 7077 port check"
fi

if command -v curl >/dev/null 2>&1; then
  check_cmd "Spark Master UI http://$MASTER_HOST:8080" curl -fsS "http://$MASTER_HOST:8080"
else
  echo "WARN: curl not found, skip Spark UI check"
fi

echo "== Remote workers =="
for node in $NODES; do
  if [ "$node" = "$(hostname)" ] || [ "$node" = "$MASTER_HOST" ]; then
    echo "INFO: $node local or master node, inspect jps output above"
  else
    ssh "$node" "jps | grep -E 'Worker|Master'" || {
      echo "WARN: cannot verify Spark process on $node"
      status=1
    }
  fi
done

echo "== Optional SparkPi smoke test =="
example_jar=$(ls "$SPARK_HOME"/examples/jars/spark-examples*.jar 2>/dev/null | head -n 1)
if [ -n "$example_jar" ]; then
  "$SPARK_HOME/bin/spark-submit" --master "$MASTER_URL" --class org.apache.spark.examples.SparkPi "$example_jar" 10 >/tmp/spark_pi.out 2>&1 \
    && echo "OK: SparkPi submitted" \
    || { echo "WARN: SparkPi failed"; cat /tmp/spark_pi.out; status=1; }
else
  echo "WARN: Spark examples jar not found, skip SparkPi"
fi

if [ "$status" -eq 0 ]; then
  echo "OK: Spark cluster check completed"
else
  echo "WARN: Spark cluster check found issues"
fi
exit "$status"
