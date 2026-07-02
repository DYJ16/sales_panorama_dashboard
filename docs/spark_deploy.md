# Spark 集群部署说明

## 集群角色

- node1：Master + Worker
- node2：Worker
- node3：Worker
- Spark Master：`spark://node1:7077`
- Spark 安装目录：`/export/server/spark`

## 环境检查

```bash
java -version
/export/server/spark/bin/spark-submit --version
jps
```

node1 应看到 `Master` 和 `Worker`，node2/node3 应看到 `Worker`。

## 启动集群

```bash
cd /export/server/spark/sbin
./start-all.sh
```

Web UI：

```text
http://node1:8080
```

## SQL Server JDBC 驱动

Spark 通过 JDBC 读取 SQL Server，需要准备 `mssql-jdbc.jar`：

```text
/export/server/spark/jars/mssql-jdbc.jar
```

提交任务时通过 `--jars` 加载。

## 提交销售计算任务

```bash
cd /export/server/project/sales_panorama_dashboard

/export/server/spark/bin/spark-submit \
  --master spark://node1:7077 \
  --name EnterpriseSalesPanoramaSpark \
  --jars /export/server/spark/jars/mssql-jdbc.jar \
  backend/spark_jobs/sales_spark_job.py
```

或运行：

```bash
bash scripts/run_spark_job.sh
```

正式版本禁止使用 `local[*]` 作为最终运行模式。

## 常见问题

- 7077 不通：检查 Master 是否启动、防火墙和 `/etc/hosts`。
- Worker 不显示：检查 node2/node3 的 SSH、Spark 配置和 Worker 进程。
- JDBC 连接失败：检查 SQL Server 1433、账号密码、`encrypt=true;trustServerCertificate=true`。
- 输出文件缺失：查看 Spark 控制台日志和 `output/spark_result` 权限。
