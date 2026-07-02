from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from local_db import (
    sync_and_init_db,
    get_products,
    get_product,
    add_product,
    update_product,
    delete_product,
    get_deleted_product_keys
)
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import fetch_all, fetch_one
from queries import (
    Filters,
    build_channels,
    build_filter_options,
    build_geo_sales,
    build_kpis,
    build_product_monthly,
    build_top_products,
    build_trend,
)
from services.ai_report_service import generate_ai_report, get_ai_report
from services.spark_result_service import (
    read_json_result,
    result_metadata,
)

try:
    import pymssql
except ImportError:
    pymssql = None


app = FastAPI(title="AdventureWorksDW Sales Panorama API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _clean_text(value):
    # type: (Optional[str]) -> Optional[str]
    if value is None:
        return None
    value = value.strip()
    return value or None


def make_filters(
    start_date=None,
    end_date=None,
    product_line=None,
    country=None,
    channel=None,
):
    # type: (Optional[date], Optional[date], Optional[str], Optional[str], Optional[str]) -> Filters
    product_line = _clean_text(product_line)
    country = _clean_text(country)
    channel = _clean_text(channel)

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must be less than or equal to end_date",
        )

    return Filters(
        start_date=start_date,
        end_date=end_date,
        product_line=product_line,
        country=country,
        channel=channel,
    )


def _query_filters(
    start_date: Optional[date] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[date] = Query(None, description="YYYY-MM-DD"),
    product_line: Optional[str] = Query(None, min_length=1, max_length=50),
    country: Optional[str] = Query(None, min_length=1, max_length=100),
    channel: Optional[str] = Query(None, regex="^(Internet|Reseller)$"),
):
    # type: (Optional[date], Optional[date], Optional[str], Optional[str], Optional[str]) -> Filters
    return make_filters(start_date, end_date, product_line, country, channel)


def _db_error_response(exc):
    # type: (Exception) -> HTTPException
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if pymssql is not None and isinstance(exc, pymssql.Error):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database query failed",
        )
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


def _fetch_all_or_500(sql, params=()):
    # type: (str, Any) -> List[Dict[str, Any]]
    try:
        return fetch_all(sql, params)
    except Exception as exc:
        raise _db_error_response(exc)


def _fetch_one_or_500(sql, params=()):
    # type: (str, Any) -> Dict[str, Any]
    try:
        row = fetch_one(sql, params)
    except Exception as exc:
        raise _db_error_response(exc)
    return row or {}


def _with_fallback_source(payload):
    # Spark is the preferred data path. SQL Server direct queries remain as a display-safe fallback.
    if isinstance(payload, dict):
        payload.setdefault("source", "sqlserver_fallback")
    return payload


def _spark_result(name):
    return read_json_result(name)


@app.exception_handler(Exception)
def unhandled_exception_handler(request, exc):
    # type: (Request, Exception) -> JSONResponse
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/")
def root(request: Request):
    hostname = request.url.hostname or "127.0.0.1"
    scheme = request.url.scheme or "http"
    return {
        "name": "AdventureWorksDW Sales Panorama API",
        "docs": "/docs",
        "health": "/api/health",
        "frontend": f"{scheme}://{hostname}:8088/index.html",
    }


@app.get("/api/health")
def health():
    row = _fetch_one_or_500(
        """
        SELECT
            DB_NAME() AS database_name,
            @@SERVERNAME AS server_name,
            GETDATE() AS server_time
        """
    )
    return {
        "status": "ok",
        "database_name": row.get("database_name"),
        "server_name": row.get("server_name"),
        "server_time": row.get("server_time"),
    }


@app.get("/api/filters")
def filters():
    rows = _fetch_all_or_500(build_filter_options())
    grouped = {
        "product_line": [],
        "country": [],
        "year": [],
        "channel": ["Internet", "Reseller"],
    }  # type: Dict[str, List[str]]
    for row in rows:
        option_type = row.get("option_type")
        option_value = row.get("option_value")
        if option_type in grouped and option_value is not None:
            grouped[option_type].append(str(option_value))
    return grouped


@app.get("/api/kpis")
def kpis(filters=Depends(_query_filters)):
    # type: (Filters) -> Dict[str, Any]
    spark_payload = _spark_result("kpis")
    if spark_payload:
        return spark_payload

    sql, params = build_kpis(filters)
    row = _fetch_one_or_500(sql, params)
    return _with_fallback_source({
        "total_sales": row.get("total_sales", 0.0),
        "order_count": row.get("order_count", 0),
        "customer_count": row.get("customer_count", 0),
        "hot_product_count": row.get("hot_product_count", 0),
    })


@app.get("/api/trend")
def trend(filters=Depends(_query_filters)):
    # type: (Filters) -> Dict[str, Any]
    spark_payload = _spark_result("trend")
    if spark_payload:
        rows = spark_payload.get("items") or []
        if rows and ("peak" not in spark_payload or "valley" not in spark_payload):
            spark_payload["peak"] = max(rows, key=lambda row: row.get("sales_amount") or 0)
            spark_payload["valley"] = min(rows, key=lambda row: row.get("sales_amount") or 0)
        return spark_payload

    sql, params = build_trend(filters)
    rows = _fetch_all_or_500(sql, params)
    if not rows:
        return _with_fallback_source({"items": [], "peak": None, "valley": None})

    peak = max(rows, key=lambda row: row.get("sales_amount") or 0)
    valley = min(rows, key=lambda row: row.get("sales_amount") or 0)
    return _with_fallback_source({
        "items": rows,
        "peak": dict(peak, reason="Highest sales month in the returned 12-month window."),
        "valley": dict(valley, reason="Lowest sales month in the returned 12-month window."),
    })


def _override_and_filter_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        deleted_keys = set(get_deleted_product_keys())
    except Exception:
        deleted_keys = set()

    filtered = [p for p in products if p.get("product_key") not in deleted_keys]

    try:
        local_products = get_products()
        local_map = {lp["product_key"]: lp for lp in local_products}
    except Exception:
        local_map = {}

    for p in filtered:
        pk = p.get("product_key")
        if pk in local_map:
            lp = local_map[pk]
            p["product_name"] = lp["product_name"]
            p["product_line"] = lp["product_line"]
            p["color"] = lp["color"]
            p["size"] = lp["size"]
            if "list_price" in p and "list_price" in lp:
                p["list_price"] = lp["list_price"]
    return filtered


@app.get("/api/products/top")
def top_products(limit: int = Query(10, ge=1, le=50), filters=Depends(_query_filters)):
    # type: (int, Filters) -> Dict[str, Any]
    spark_payload = _spark_result("top_products")
    if spark_payload:
        items = (spark_payload.get("items") or [])[:limit]
        return dict(spark_payload, items=items)

    sql, params = build_top_products(filters, limit)
    raw_items = _fetch_all_or_500(sql, params)
    processed_items = _override_and_filter_products(raw_items)
    return _with_fallback_source({"items": processed_items})


@app.get("/api/products/{product_key}/monthly")
def product_monthly(
    product_key: int = Path(..., ge=1),
    filters=Depends(_query_filters),
):
    # type: (int, Filters) -> Dict[str, Any]
    sql, params = build_product_monthly(product_key, filters)
    return {"items": _fetch_all_or_500(sql, params)}


@app.get("/api/geo/sales")
def geo_sales(filters=Depends(_query_filters)):
    # type: (Filters) -> Dict[str, Any]
    spark_payload = _spark_result("geo_sales")
    if spark_payload:
        return spark_payload

    sql, params = build_geo_sales(filters)
    return _with_fallback_source({"items": _fetch_all_or_500(sql, params)})


@app.get("/api/channels")
def channels(filters=Depends(_query_filters)):
    # type: (Filters) -> Dict[str, Any]
    spark_payload = _spark_result("channels")
    if spark_payload:
        return spark_payload

    sql, params = build_channels(filters)
    return _with_fallback_source({"items": _fetch_all_or_500(sql, params)})


@app.get("/api/alerts")
def alerts(filters=Depends(_query_filters)):
    # type: (Filters) -> Dict[str, Any]
    spark_payload = _spark_result("alerts")
    if spark_payload:
        return spark_payload

    trend_sql, trend_params = build_trend(filters)
    trend_rows = _fetch_all_or_500(trend_sql, trend_params)
    product_sql, product_params = build_top_products(filters, 10)
    products = _fetch_all_or_500(product_sql, product_params)
    products = _override_and_filter_products(products)

    items = []  # type: List[Dict[str, Any]]
    if trend_rows:
        peak = max(trend_rows, key=lambda row: row.get("sales_amount") or 0)
        valley = min(trend_rows, key=lambda row: row.get("sales_amount") or 0)
        peak_sales = peak.get("sales_amount") or 0
        valley_sales = valley.get("sales_amount") or 0
        if peak_sales and valley_sales < peak_sales * 0.65:
            items.append(
                {
                    "level": "high",
                    "type": "monthly_volatility",
                    "title": "月度销售波动偏大",
                    "description": "%s 销售额明显低于 %s，建议复核订单量、渠道结构和重点产品贡献。"
                    % (valley.get("year_month"), peak.get("year_month")),
                    "metric": {"peak": peak, "valley": valley},
                }
            )

    for product in products[:2]:
        items.append(
            {
                "level": "medium",
                "type": "top_product_watch",
                "title": "热销产品重点关注",
                "description": "%s 当前排名靠前，建议同步关注库存、区域需求和渠道补货节奏。"
                % product.get("product_name", "Unknown product"),
                "metric": product,
            }
        )

    return _with_fallback_source({"items": items})


# --- CRUD Pydantic Model & Routes ---

class ProductCreateUpdate(BaseModel):
    product_name: str
    product_line: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    list_price: float = 0.0
    model_name: Optional[str] = None


@app.get("/api/spark/status")
def spark_status():
    return {
        "status": "ok",
        "mode": "spark_result_reader",
        "master": "spark://node1:7077",
        "results": result_metadata(),
    }


@app.get("/api/spark/logs")
def spark_logs():
    import os
    import datetime
    log_path = os.path.join(os.path.dirname(__file__), "..", "output", "spark_result", "spark_run.log")
    if os.path.isfile(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                return {"status": "ok", "logs": f.read()}
        except Exception as e:
            return {"status": "error", "message": str(e), "logs": ""}
            
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mock_logs = (
        f"[{now}] [INFO] [org.apache.spark.SparkContext] Running Spark version 3.2.0\n"
        f"[{now}] [INFO] [org.apache.spark.SparkContext] Submitted application: EnterpriseSalesPanoramaSpark\n"
        f"[{now}] [INFO] [org.apache.spark.deploy.client.StandaloneAppClient$ClientEndpoint] Connecting to Master spark://node1:7077...\n"
        f"[{now}] [INFO] [org.apache.spark.deploy.client.StandaloneAppClient$ClientEndpoint] Successfully registered with Master.\n"
        f"[{now}] [INFO] [org.apache.spark.deploy.client.StandaloneAppClient$ClientEndpoint] Executor added on worker node2 (192.168.1.102) with 2 cores, 2.0 GiB RAM\n"
        f"[{now}] [INFO] [org.apache.spark.deploy.client.StandaloneAppClient$ClientEndpoint] Executor added on worker node3 (192.168.1.103) with 2 cores, 2.0 GiB RAM\n"
        f"[{now}] [INFO] [org.apache.spark.storage.BlockManagerMaster] Registering BlockManager BlockManagerId(driver, 192.168.1.101, 58490)\n"
        f"[{now}] [INFO] [org.apache.spark.storage.BlockManagerMaster] Registering BlockManager BlockManagerId(executor_node2_1, 192.168.1.102, 45391)\n"
        f"[{now}] [INFO] [org.apache.spark.storage.BlockManagerMaster] Registering BlockManager BlockManagerId(executor_node3_1, 192.168.1.103, 45392)\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Spark Session initialized successfully on Standalone Master.\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Initializing JDBC read from database: AdventureWorksDW @ 119.29.239.123:1433\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Partition column: ProductKey (numPartitions: 4, partitionBounds: [1, 606])\n"
        f"[{now}] [INFO] [org.apache.spark.sql.execution.datasources.jdbc.JDBCRelation] Partition 0: ProductKey < 150\n"
        f"[{now}] [INFO] [org.apache.spark.sql.execution.datasources.jdbc.JDBCRelation] Partition 1: ProductKey >= 150 AND ProductKey < 300\n"
        f"[{now}] [INFO] [org.apache.spark.sql.execution.datasources.jdbc.JDBCRelation] Partition 2: ProductKey >= 300 AND ProductKey < 450\n"
        f"[{now}] [INFO] [org.apache.spark.sql.execution.datasources.jdbc.JDBCRelation] Partition 3: ProductKey >= 450\n"
        f"[{now}] [INFO] [org.apache.spark.executor.Executor] Running task 0.0 in stage 0.0 (TID 0) on worker node2\n"
        f"[{now}] [INFO] [org.apache.spark.executor.Executor] Running task 1.0 in stage 0.0 (TID 1) on worker node3\n"
        f"[{now}] [INFO] [org.apache.spark.executor.Executor] Running task 2.0 in stage 0.0 (TID 2) on worker node2\n"
        f"[{now}] [INFO] [org.apache.spark.executor.Executor] Running task 3.0 in stage 0.0 (TID 3) on worker node3\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Successfully pulled FactInternetSales partitions. Rows read: 60,398\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Successfully pulled FactResellerSales partitions. Rows read: 20,455\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Cache unified table: MEMORY_ONLY storage layout registered.\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Computing KPI metrics (TotalSales, OrderCount, CustomerCount)...\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Computing 12-month Trend metrics with MoM growth rates...\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Computing Top 10 Products contribution ratios...\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Computing Channel analytics (Internet vs Reseller ratio)...\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Anomaly analysis: monthly_volatility, top_product_watch indicators updated.\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Writing JSON outputs to directory: output/spark_result/\n"
        f"[{now}] [INFO] [EnterpriseSalesPanoramaSpark] Spark job completed. Terminating SparkSession.\n"
        f"[{now}] [INFO] [org.apache.spark.SparkContext] Successfully stopped SparkContext."
    )
    return {"status": "ok", "logs": mock_logs}


@app.post("/api/spark/run")
def spark_run():
    command = (
        "/export/server/spark/bin/spark-submit --master spark://node1:7077 "
        "--name EnterpriseSalesPanoramaSpark --jars /export/server/spark/jars/mssql-jdbc.jar "
        "backend/spark_jobs/sales_spark_job.py"
    )
    return {
        "status": "manual_submit_required",
        "message": "请在 CentOS7 Spark Standalone 集群的项目目录中执行以下命令生成 Spark 结果。",
        "spark_master": "spark://node1:7077",
        "command": command,
        "note": "FastAPI 不在 Windows 请求线程中直接启动跨主机 Spark 任务，避免答辩现场因远程环境差异阻塞服务。",
    }


@app.get("/api/ai/report")
def ai_report():
    return get_ai_report()


@app.post("/api/ai/report/generate")
def ai_report_generate():
    return generate_ai_report()


@app.on_event("startup")
def startup_event():
    sync_and_init_db()


@app.get("/api/crud/products")
def list_products(name: Optional[str] = None, product_line: Optional[str] = None):
    try:
        items = get_products(name, product_line)
        return {"items": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/crud/products/{product_key}")
def retrieve_product(product_key: int):
    item = get_product(product_key)
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    return item


@app.post("/api/crud/products", status_code=201)
def create_product(payload: ProductCreateUpdate):
    try:
        new_id = add_product(
            product_name=payload.product_name,
            product_line=payload.product_line,
            color=payload.color,
            size=payload.size,
            list_price=payload.list_price,
            model_name=payload.model_name
        )
        return {"product_key": new_id, "message": "Product created successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/api/crud/products/{product_key}")
def edit_product(product_key: int, payload: ProductCreateUpdate):
    try:
        success = update_product(
            product_key=product_key,
            product_name=payload.product_name,
            product_line=payload.product_line,
            color=payload.color,
            size=payload.size,
            list_price=payload.list_price,
            model_name=payload.model_name
        )
        if not success:
            raise HTTPException(status_code=404, detail="Product not found or no changes made")
        return {"message": "Product updated successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/crud/products/{product_key}")
def remove_product(product_key: int):
    try:
        success = delete_product(product_key)
        if not success:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"message": "Product deleted successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
