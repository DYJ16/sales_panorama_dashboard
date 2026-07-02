# 运行指南

## Windows 本地演示

安装依赖：

```powershell
cd C:\Users\PXHONY\Desktop\spark\dashboard\backend
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

启动：

```powershell
cd C:\Users\PXHONY\Desktop\spark\dashboard
.\start.bat
```

访问：

```text
http://127.0.0.1:8088/index.html
```

后端：

```text
http://127.0.0.1:8000
```

## SQL Server 配置

FastAPI 兼容以下环境变量：

```powershell
$env:DB_SERVER="119.29.239.123"
$env:DB_DATABASE="AdventureWorksDW"
$env:DB_USER="readonlyuser"
$env:DB_PASSWORD="你的密码"
```

Spark JDBC 使用：

```bash
export SQLSERVER_HOST=119.29.239.123
export SQLSERVER_PORT=1433
export SQLSERVER_DATABASE=AdventureWorksDW
export SQLSERVER_USER=readonlyuser
export SQLSERVER_PASSWORD=你的密码
export SQLSERVER_TRUST_CERTIFICATE=true
```

JDBC URL 会使用：

```text
encrypt=true;trustServerCertificate=true
```

用于处理 SQL Server Driver 18 常见证书信任问题。

## Linux Spark 正式流程

### 一键运行

推荐优先使用一键脚本。脚本会先检查 Java、Spark、Python、JDBC 驱动、项目文件、端口和 Spark 输出文件，再执行 Spark 计算、生成 AI 报告并启动后端和前端：

```bash
cd /export/server/project/sales_panorama_dashboard
bash scripts/start.sh
```

如果 SQL Server JDBC 驱动不在默认位置，可以手动指定：

```bash
JDBC_JAR=/export/server/spark/jars/mssql-jdbc-12.8.1.jre8.jar bash scripts/start.sh
```

停止后端和前端：

```bash
bash scripts/stop.sh
```

如果只想检查环境和生成 Spark/AI 结果，不启动 Web 服务：

```bash
START_SERVERS=0 bash scripts/start.sh
```

CentOS7 正式 Spark 部署不强制安装 `pymssql`。后端会优先读取 `output/spark_result/*.json`，SQL Server 实时回退才需要额外安装 `pymssql`。

如果缺少 JDBC 驱动，先把 Microsoft SQL Server JDBC Driver 的 jar 放到以下任一位置：

```text
/export/server/spark/jars/mssql-jdbc.jar
/export/server/project/sales_panorama_dashboard/lib/mssql-jdbc.jar
```

### 手动流程

1. 启动 Spark 集群：

```bash
cd /export/server/spark/sbin
./start-all.sh
```

2. 检查集群：

```bash
bash scripts/check_spark_cluster.sh
```

3. 提交 Spark 任务：

```bash
bash scripts/run_spark_job.sh
```

4. 生成 AI 报告：

```bash
export DEEPSEEK_API_KEY=你的_API_KEY
export DEEPSEEK_MODEL=deepseek-v4-flash
bash scripts/generate_ai_report.sh
```

5. 启动 FastAPI：

```bash
cd backend
uvicorn app:app --host 0.0.0.0 --port 8000
```

6. 启动前端：

```bash
cd frontend
python -m http.server 8088
```

## 数据接口优先级

经营分析接口优先读取：

```text
output/spark_result/*.json
```

如果 Spark 结果不存在，当前实现会回退到 SQL Server 实时查询，并在响应中标注 `source=sqlserver_fallback`，保证大屏展示稳定。
