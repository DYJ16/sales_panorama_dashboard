import json
import os
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from spark_config import get_output_dir, get_sqlserver_jdbc_config
from sqlserver_reader import read_core_tables


def write_json(name, payload):
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, name)
    enriched = dict(payload)
    enriched.setdefault("source", "spark")
    enriched.setdefault("generated_at", datetime.utcnow().isoformat(timespec="seconds") + "Z")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)


def rows_to_dicts(rows):
    return [row.asDict(recursive=True) for row in rows]


def build_unified_sales(tables):
    internet = tables["internet_sales"].select(
        F.lit("Internet").alias("sales_channel"),
        F.col("OrderDateKey").alias("order_date_key"),
        F.col("ProductKey").alias("product_key"),
        F.col("CustomerKey").alias("customer_key"),
        F.col("SalesOrderNumber").alias("sales_order_number"),
        F.col("SalesAmount").cast("double").alias("sales_amount"),
    )
    reseller = tables["reseller_sales"].select(
        F.lit("Reseller").alias("sales_channel"),
        F.col("OrderDateKey").alias("order_date_key"),
        F.col("ProductKey").alias("product_key"),
        F.lit(None).cast("int").alias("customer_key"),
        F.col("SalesOrderNumber").alias("sales_order_number"),
        F.col("SalesAmount").cast("double").alias("sales_amount"),
    )
    return internet.unionByName(reseller)


def add_dimensions(unified, tables):
    date_dim = tables["date"].select(
        F.col("DateKey").alias("date_key"),
        F.col("FullDateAlternateKey").alias("full_date"),
        F.col("CalendarYear").alias("year"),
        F.col("MonthNumberOfYear").alias("month"),
    )
    product_dim = tables["product"].select(
        F.col("ProductKey").alias("dim_product_key"),
        F.col("EnglishProductName").alias("product_name"),
        F.coalesce(F.col("ProductLine"), F.lit("Unknown")).alias("product_line"),
        F.coalesce(F.col("Color"), F.lit("Unknown")).alias("color"),
        F.coalesce(F.col("Size"), F.lit("Unknown")).alias("size"),
    )
    customer_geo = (
        tables["customer"]
        .select(F.col("CustomerKey").alias("dim_customer_key"), F.col("GeographyKey").alias("customer_geography_key"))
        .join(
            tables["geography"].select(
                F.col("GeographyKey").alias("geo_key"),
                F.col("EnglishCountryRegionName").alias("country"),
                F.col("StateProvinceName").alias("state_province"),
                F.col("City").alias("city"),
            ),
            F.col("customer_geography_key") == F.col("geo_key"),
            "left",
        )
    )
    return (
        unified.join(date_dim, unified.order_date_key == date_dim.date_key, "left")
        .join(product_dim, unified.product_key == product_dim.dim_product_key, "left")
        .join(customer_geo, unified.customer_key == customer_geo.dim_customer_key, "left")
    )


def compute_kpis(sales):
    row = sales.agg(
        F.sum("sales_amount").alias("total_sales"),
        F.countDistinct("sales_order_number").alias("order_count"),
        F.countDistinct("customer_key").alias("customer_count"),
        F.countDistinct("product_key").alias("product_count"),
    ).first()
    total_sales = float(row["total_sales"] or 0)
    order_count = int(row["order_count"] or 0)
    return {
        "total_sales": total_sales,
        "order_count": order_count,
        "customer_count": int(row["customer_count"] or 0),
        "hot_product_count": int(row["product_count"] or 0),
        "product_count": int(row["product_count"] or 0),
        "avg_order_value": round(total_sales / order_count, 2) if order_count else 0,
    }


def compute_trend(sales):
    monthly = (
        sales.groupBy("year", "month")
        .agg(F.sum("sales_amount").alias("sales_amount"), F.countDistinct("sales_order_number").alias("order_count"))
        .withColumn("year_month", F.concat_ws("-", F.col("year"), F.lpad(F.col("month"), 2, "0")))
        .orderBy("year", "month")
    )
    rows = rows_to_dicts(monthly.collect())
    previous = None
    for item in rows:
        amount = float(item.get("sales_amount") or 0)
        item["sales_amount"] = round(amount, 2)
        item["order_count"] = int(item.get("order_count") or 0)
        if previous and previous > 0:
            growth = (amount - previous) / previous
        else:
            growth = 0
        item["mom_growth_rate"] = round(growth, 4)
        item["trend_direction"] = "up" if growth > 0.02 else "down" if growth < -0.02 else "stable"
        previous = amount
    return rows


def compute_channels(sales):
    total = sales.agg(F.sum("sales_amount").alias("total")).first()["total"] or 0
    rows = rows_to_dicts(
        sales.groupBy("sales_channel")
        .agg(F.sum("sales_amount").alias("sales_amount"), F.countDistinct("sales_order_number").alias("order_count"))
        .orderBy(F.desc("sales_amount"))
        .collect()
    )
    for item in rows:
        sales_amount = float(item.get("sales_amount") or 0)
        orders = int(item.get("order_count") or 0)
        ratio = sales_amount / total if total else 0
        item["sales_amount"] = round(sales_amount, 2)
        item["order_count"] = orders
        item["sales_ratio"] = round(ratio, 4)
        item["order_ratio"] = 0
        item["avg_order_amount"] = round(sales_amount / orders, 2) if orders else 0
        item["performance_summary"] = "主力渠道" if ratio >= 0.5 else "补充渠道"
    order_total = sum(item["order_count"] for item in rows) or 1
    for item in rows:
        item["order_ratio"] = round(item["order_count"] / order_total, 4)
    return rows


def compute_top_products(sales):
    total = sales.agg(F.sum("sales_amount").alias("total")).first()["total"] or 0
    rows = rows_to_dicts(
        sales.groupBy("product_key", "product_name", "product_line", "color", "size")
        .agg(F.sum("sales_amount").alias("sales_amount"), F.countDistinct("sales_order_number").alias("order_count"))
        .orderBy(F.desc("sales_amount"))
        .limit(10)
        .collect()
    )
    for item in rows:
        amount = float(item.get("sales_amount") or 0)
        contribution = amount / total if total else 0
        item["sales_amount"] = round(amount, 2)
        item["order_count"] = int(item.get("order_count") or 0)
        item["contribution_rate"] = round(contribution, 4)
        item["product_health"] = "高贡献产品" if contribution >= 0.08 else "稳定产品"
    return rows


def compute_geo(sales):
    geo_sales = sales.filter(F.col("country").isNotNull())
    rows = rows_to_dicts(
        geo_sales.groupBy("country", "state_province", "city")
        .agg(
            F.sum("sales_amount").alias("sales_amount"),
            F.countDistinct("customer_key").alias("customer_count"),
            F.countDistinct("sales_order_number").alias("order_count"),
        )
        .orderBy(F.desc("sales_amount"))
        .limit(100)
        .collect()
    )
    if not rows:
        return []
    max_sales = max(float(item.get("sales_amount") or 0) for item in rows) or 1
    for item in rows:
        amount = float(item.get("sales_amount") or 0)
        item["sales_amount"] = round(amount, 2)
        item["customer_count"] = int(item.get("customer_count") or 0)
        item["order_count"] = int(item.get("order_count") or 0)
        item["region_level"] = "高价值区域" if amount >= max_sales * 0.65 else "潜力区域"
    return rows


def compute_alerts(kpis, trend, products, channels, geo):
    alerts = []
    if len(trend) >= 2:
        last = trend[-1]
        previous = trend[-2]
        if last.get("sales_amount", 0) < previous.get("sales_amount", 0) * 0.85:
            alerts.append(
                {
                    "level": "high",
                    "type": "sales_drop",
                    "title": "销售额突然下降",
                    "description": "%s 销售额较上月明显下降，建议复核渠道补货和重点订单变化。"
                    % last.get("year_month"),
                    "metric": {"current": last, "previous": previous},
                }
            )
    if products:
        top_rate = products[0].get("contribution_rate", 0)
        if top_rate >= 0.18:
            alerts.append(
                {
                    "level": "medium",
                    "type": "top_product_dependency",
                    "title": "Top 产品依赖风险",
                    "description": "头部产品贡献率较高，建议关注库存、价格和替代产品储备。",
                    "metric": products[0],
                }
            )
    if channels:
        max_channel = max(channels, key=lambda item: item.get("sales_ratio", 0))
        if max_channel.get("sales_ratio", 0) >= 0.75:
            alerts.append(
                {
                    "level": "medium",
                    "type": "channel_imbalance",
                    "title": "渠道结构偏集中",
                    "description": "%s 渠道销售占比偏高，建议评估渠道风险和增长可持续性。"
                    % max_channel.get("sales_channel"),
                    "metric": max_channel,
                }
            )
    if geo:
        alerts.append(
            {
                "level": "info",
                "type": "high_value_region",
                "title": "高价值区域识别",
                "description": "%s 当前销售表现领先，可作为区域经营策略样板。"
                % (geo[0].get("country") or geo[0].get("city") or "重点区域"),
                "metric": geo[0],
            }
        )
    if not alerts:
        alerts.append(
            {
                "level": "info",
                "type": "stable_operation",
                "title": "经营状态整体平稳",
                "description": "Spark 计算结果未发现显著异常，建议持续跟踪趋势、渠道和重点产品结构。",
                "metric": kpis,
            }
        )
    return alerts


def main():
    spark = (
        SparkSession.builder.appName("EnterpriseSalesPanoramaSpark")
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
        .getOrCreate()
    )
    try:
        config = get_sqlserver_jdbc_config()
        print("Reading SQL Server %s:%s/%s by JDBC" % (config["host"], config["port"], config["database"]))
        tables = read_core_tables(spark)
        sales = add_dimensions(build_unified_sales(tables), tables).cache()
        kpis = compute_kpis(sales)
        trend = compute_trend(sales)
        channels = compute_channels(sales)
        products = compute_top_products(sales)
        geo = compute_geo(sales)
        alerts = compute_alerts(kpis, trend, products, channels, geo)

        write_json("kpis.json", kpis)
        write_json("trend.json", {"items": trend})
        write_json("channels.json", {"items": channels})
        write_json("top_products.json", {"items": products})
        write_json("geo_sales.json", {"items": geo})
        write_json("alerts.json", {"items": alerts})
        print("Spark results written to %s" % get_output_dir())
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
