# CentOS7 部署与启动说明

本文档记录本项目在 CentOS7 + Spark Standalone 集群上的实际运行步骤。

## 当前端口

| 服务 | 端口 | 地址 |
|---|---:|---|
| FastAPI 后端 | 8002 | `http://node1:8002` |
| 前端页面 | 8090 | `http://node1:8090/index.html?v=20260630` |
| Spark Master UI | 8080 | `http://node1:8080` |

如果浏览器无法解析 `node1`，请改用 node1 的实际 IP，例如：

```text
http://192.168.88.101:8090/index.html?v=20260630
```

## 1. 解压项目

```bash
mkdir -p /export/server/project
tar -xzf sales_panorama_dashboard.tar.gz -C /export/server/project
cd /export/server/project/sales_panorama_dashboard
```

## 2. 准备 Python 虚拟环境

不要把依赖装进 Anaconda `base` 环境，使用项目目录下的 `.venv`：

```bash
cd /export/server/project/sales_panorama_dashboard
/export/server/anaconda3/bin/python3 -m venv .venv
.venv/bin/python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.txt
```

验证依赖：

```bash
.venv/bin/python - <<'PY'
import fastapi, uvicorn, requests
print("python deps ok")
PY
```

看到 `python deps ok` 表示成功。

## 3. 准备 SQL Server JDBC 驱动

Spark 读取 SQL Server 需要 Microsoft JDBC 驱动。推荐放到：

```text
/export/server/spark/jars/mssql-jdbc.jar
```

检查：

```bash
ls -lh /export/server/spark/jars/mssql-jdbc.jar
```

如果驱动文件名不同，运行 Spark 时指定：

```bash
JDBC_JAR=/export/server/spark/jars/mssql-jdbc-12.8.1.jre8.jar bash scripts/run_spark_job.sh
```

## 4. 启动或确认 Spark 集群

检查进程：

```bash
jps
```

node1 正常应有 `Master` 和 `Worker`。如果没有，启动 Spark：

```bash
cd /export/server/spark/sbin
./start-master.sh
./start-worker.sh spark://node1:7077
```

如果集群是 HA 模式，提交地址和 Worker 地址应使用多个 Master：

```bash
spark://node1:7077,node2:7077,node3:7077
```

## 5. 执行 Spark 计算

单 Master 模式：

```bash
cd /export/server/project/sales_panorama_dashboard
bash scripts/run_spark_job.sh
```

HA 模式：

```bash
cd /export/server/project/sales_panorama_dashboard
MASTER_URL=spark://node1:7077,node2:7077,node3:7077 bash scripts/run_spark_job.sh
```

成功时终端末尾应看到：

```text
Spark results written to /export/server/project/sales_panorama_dashboard/output/spark_result
OK: Spark results written to /export/server/project/sales_panorama_dashboard/output/spark_result
```

检查输出文件：

```bash
ls -lh output/spark_result
```

应包含：

```text
kpis.json
trend.json
top_products.json
channels.json
geo_sales.json
alerts.json
```

## 6. 修改前端后端端口

本机 8000/8001 已被 Docker 服务占用，因此后端使用 8002。确认前端请求端口已经改为 8002：

```bash
cd /export/server/project/sales_panorama_dashboard
sed -i 's/:8000/:8002/g' frontend/index.html
grep -n "8002" frontend/index.html | head
```

## 7. 启动后端

如果 8002 被占用，先处理：

```bash
ss -lntp | grep 8002
fuser -k 8002/tcp
```

启动后端：

```bash
cd /export/server/project/sales_panorama_dashboard/backend
../.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8002
```

验证后端：

```bash
curl http://127.0.0.1:8002/api/spark/status
```

正常返回中应包含：

```json
{"status":"ok","mode":"spark_result_reader"}
```

## 8. 启动前端

如果 8090 被占用，先处理：

```bash
ss -lntp | grep 8090
fuser -k 8090/tcp
```

启动前端：

```bash
cd /export/server/project/sales_panorama_dashboard/frontend
../.venv/bin/python -m http.server 8090 --bind 0.0.0.0
```

访问：

```text
http://node1:8090/index.html?v=20260630
```

## 9. 后台运行方式

创建日志目录：

```bash
mkdir -p /export/server/project/sales_panorama_dashboard/output/logs
```

后台启动后端：

```bash
cd /export/server/project/sales_panorama_dashboard/backend
nohup ../.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8002 > ../output/logs/backend.log 2>&1 &
```

后台启动前端：

```bash
cd /export/server/project/sales_panorama_dashboard/frontend
nohup ../.venv/bin/python -m http.server 8090 --bind 0.0.0.0 > ../output/logs/frontend.log 2>&1 &
```

查看日志：

```bash
tail -f /export/server/project/sales_panorama_dashboard/output/logs/backend.log
tail -f /export/server/project/sales_panorama_dashboard/output/logs/frontend.log
```

## 10. 常见问题

### 端口被占用

查看端口：

```bash
ss -lntp | grep 端口号
```

释放端口：

```bash
fuser -k 端口号/tcp
```

### 后端返回 Endpoint not found

说明访问到的不是本项目新版后端，通常是端口被其他服务占用。请确认访问的是：

```text
http://127.0.0.1:8002/api/spark/status
```

### Spark 提示 All masters are unresponsive

说明 Spark Master 地址不可达。检查：

```bash
jps
ss -lntp | grep 7077
getent hosts node1 node2 node3
```

如果是 HA 模式，使用：

```bash
MASTER_URL=spark://node1:7077,node2:7077,node3:7077 bash scripts/run_spark_job.sh
```

### 不要强制安装 pymssql

CentOS7 正式链路使用 Spark JDBC 读取 SQL Server，后端优先读取 Spark JSON 结果，不强制依赖 `pymssql`。
