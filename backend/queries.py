from dataclasses import dataclass
from datetime import date
from typing import Any, List, Optional, Tuple


@dataclass(frozen=True)
class Filters:
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    product_line: Optional[str] = None
    country: Optional[str] = None
    channel: Optional[str] = None


UNIFIED_SALES_CTE = """
WITH UnifiedSales AS (
    SELECT
        'Internet' AS SalesChannel,
        fis.OrderDateKey,
        fis.ProductKey,
        fis.CustomerKey,
        fis.SalesOrderNumber,
        CAST(fis.SalesAmount AS decimal(18, 2)) AS SalesAmount,
        g.EnglishCountryRegionName AS CountryRegion
    FROM dbo.FactInternetSales fis
    LEFT JOIN dbo.DimCustomer c ON fis.CustomerKey = c.CustomerKey
    LEFT JOIN dbo.DimGeography g ON c.GeographyKey = g.GeographyKey
    UNION ALL
    SELECT
        'Reseller' AS SalesChannel,
        frs.OrderDateKey,
        frs.ProductKey,
        NULL AS CustomerKey,
        frs.SalesOrderNumber,
        CAST(frs.SalesAmount AS decimal(18, 2)) AS SalesAmount,
        NULL AS CountryRegion
    FROM dbo.FactResellerSales frs
)
"""


def _date_clause(alias, filters, params):
    # type: (str, Filters, List[Any]) -> str
    clauses = []
    if filters.start_date:
        clauses.append("%s.FullDateAlternateKey >= %%s" % alias)
        params.append(filters.start_date)
    if filters.end_date:
        clauses.append("%s.FullDateAlternateKey <= %%s" % alias)
        params.append(filters.end_date)
    return " AND ".join(clauses) if clauses else "1=1"


def _product_clause(alias, filters, params):
    # type: (str, Filters, List[Any]) -> str
    if not filters.product_line:
        return "1=1"
    params.append(filters.product_line)
    return "COALESCE(%s.ProductLine, 'Unknown') = %%s" % alias


def _channel_clause(alias, filters, params):
    # type: (str, Filters, List[Any]) -> str
    if filters.channel:
        params.append(filters.channel)
        return "%s.SalesChannel = %%s" % alias
    return "1=1"


def _country_clause(alias, filters, params):
    # type: (str, Filters, List[Any]) -> str
    if not filters.country:
        return "1=1"
    params.append(filters.country)
    return "%s.CountryRegion = %%s" % alias


def build_kpis(filters):
    # type: (Filters) -> Tuple[str, Tuple[Any, ...]]
    params = []  # type: List[Any]
    date_clause = _date_clause("d", filters, params)
    product_clause = _product_clause("p", filters, params)
    channel_clause = _channel_clause("us", filters, params)
    country_clause = _country_clause("us", filters, params)
    sql = """
%s,
FilteredSales AS (
    SELECT us.*
    FROM UnifiedSales us
    JOIN dbo.DimDate d ON us.OrderDateKey = d.DateKey
    JOIN dbo.DimProduct p ON us.ProductKey = p.ProductKey
    WHERE %s
      AND %s
      AND %s
      AND %s
),
ProductSales AS (
    SELECT ProductKey, SUM(SalesAmount) AS ProductSalesAmount
    FROM FilteredSales
    GROUP BY ProductKey
),
HotProducts AS (
    SELECT COUNT(*) AS HotProductCount
    FROM ProductSales
    WHERE ProductSalesAmount >= (SELECT AVG(ProductSalesAmount) FROM ProductSales)
)
SELECT
    CAST(COALESCE(SUM(fs.SalesAmount), 0) AS decimal(18, 2)) AS total_sales,
    COUNT(DISTINCT fs.SalesOrderNumber) AS order_count,
    COUNT(DISTINCT fs.CustomerKey) AS customer_count,
    COALESCE((SELECT HotProductCount FROM HotProducts), 0) AS hot_product_count
FROM FilteredSales fs;
""" % (UNIFIED_SALES_CTE, date_clause, product_clause, channel_clause, country_clause)
    return sql, tuple(params)


def build_trend(filters):
    # type: (Filters) -> Tuple[str, Tuple[Any, ...]]
    params = []  # type: List[Any]
    product_clause = _product_clause("p", filters, params)
    channel_clause = _channel_clause("us", filters, params)
    country_clause = _country_clause("us", filters, params)
    params.extend([filters.end_date, filters.end_date, filters.end_date])
    sql = """
%s,
BaseSales AS (
    SELECT us.*, d.FullDateAlternateKey, d.CalendarYear, d.MonthNumberOfYear
    FROM UnifiedSales us
    JOIN dbo.DimDate d ON us.OrderDateKey = d.DateKey
    JOIN dbo.DimProduct p ON us.ProductKey = p.ProductKey
    WHERE %s
      AND %s
      AND %s
),
EndDateValue AS (
    SELECT
        CASE
            WHEN CAST(%%s AS date) IS NULL THEN MAX(FullDateAlternateKey)
            WHEN CAST(%%s AS date) > MAX(FullDateAlternateKey) THEN MAX(FullDateAlternateKey)
            ELSE CAST(%%s AS date)
        END AS EndDate
    FROM BaseSales
)
SELECT
    b.CalendarYear AS year,
    b.MonthNumberOfYear AS month,
    CONCAT(b.CalendarYear, '-', RIGHT('0' + CAST(b.MonthNumberOfYear AS varchar(2)), 2)) AS year_month,
    CAST(SUM(b.SalesAmount) AS decimal(18, 2)) AS sales_amount,
    COUNT(DISTINCT b.SalesOrderNumber) AS order_count
FROM BaseSales b
CROSS JOIN EndDateValue e
WHERE e.EndDate IS NOT NULL
  AND b.FullDateAlternateKey >= DATEADD(MONTH, -11, DATEFROMPARTS(YEAR(e.EndDate), MONTH(e.EndDate), 1))
  AND b.FullDateAlternateKey <= e.EndDate
GROUP BY b.CalendarYear, b.MonthNumberOfYear
ORDER BY b.CalendarYear, b.MonthNumberOfYear;
""" % (UNIFIED_SALES_CTE, product_clause, channel_clause, country_clause)
    return sql, tuple(params)


def build_top_products(filters, limit=10):
    # type: (Filters, int) -> Tuple[str, Tuple[Any, ...]]
    params = []  # type: List[Any]
    date_clause = _date_clause("d", filters, params)
    product_clause = _product_clause("p", filters, params)
    channel_clause = _channel_clause("us", filters, params)
    country_clause = _country_clause("us", filters, params)
    sql = """
%s
SELECT TOP (%d)
    p.ProductKey AS product_key,
    p.EnglishProductName AS product_name,
    COALESCE(p.ProductLine, 'Unknown') AS product_line,
    COALESCE(p.Color, 'Unknown') AS color,
    COALESCE(p.Size, 'Unknown') AS size,
    CAST(SUM(us.SalesAmount) AS decimal(18, 2)) AS sales_amount,
    COUNT(DISTINCT us.SalesOrderNumber) AS order_count
FROM UnifiedSales us
JOIN dbo.DimDate d ON us.OrderDateKey = d.DateKey
JOIN dbo.DimProduct p ON us.ProductKey = p.ProductKey
WHERE %s
  AND %s
  AND %s
  AND %s
GROUP BY p.ProductKey, p.EnglishProductName, p.ProductLine, p.Color, p.Size
ORDER BY sales_amount DESC;
""" % (UNIFIED_SALES_CTE, int(limit), date_clause, product_clause, channel_clause, country_clause)
    return sql, tuple(params)


def build_product_monthly(product_key, filters):
    # type: (int, Filters) -> Tuple[str, Tuple[Any, ...]]
    params = []  # type: List[Any]
    product_clause = _product_clause("p", filters, params)
    channel_clause = _channel_clause("us", filters, params)
    country_clause = _country_clause("us", filters, params)
    params.append(product_key)
    params.extend([filters.end_date, filters.end_date, filters.end_date])
    sql = """
%s,
BaseSales AS (
    SELECT us.*, d.FullDateAlternateKey, d.CalendarYear, d.MonthNumberOfYear
    FROM UnifiedSales us
    JOIN dbo.DimDate d ON us.OrderDateKey = d.DateKey
    JOIN dbo.DimProduct p ON us.ProductKey = p.ProductKey
    WHERE %s
      AND %s
      AND %s
      AND us.ProductKey = %%s
),
EndDateValue AS (
    SELECT
        CASE
            WHEN CAST(%%s AS date) IS NULL THEN MAX(FullDateAlternateKey)
            WHEN CAST(%%s AS date) > MAX(FullDateAlternateKey) THEN MAX(FullDateAlternateKey)
            ELSE CAST(%%s AS date)
        END AS EndDate
    FROM BaseSales
)
SELECT
    b.CalendarYear AS year,
    b.MonthNumberOfYear AS month,
    CONCAT(b.CalendarYear, '-', RIGHT('0' + CAST(b.MonthNumberOfYear AS varchar(2)), 2)) AS year_month,
    CAST(SUM(b.SalesAmount) AS decimal(18, 2)) AS sales_amount,
    COUNT(DISTINCT b.SalesOrderNumber) AS order_count
FROM BaseSales b
CROSS JOIN EndDateValue e
WHERE e.EndDate IS NOT NULL
  AND b.FullDateAlternateKey >= DATEADD(MONTH, -11, DATEFROMPARTS(YEAR(e.EndDate), MONTH(e.EndDate), 1))
  AND b.FullDateAlternateKey <= e.EndDate
GROUP BY b.CalendarYear, b.MonthNumberOfYear
ORDER BY b.CalendarYear, b.MonthNumberOfYear;
""" % (UNIFIED_SALES_CTE, product_clause, channel_clause, country_clause)
    return sql, tuple(params)


def build_geo_sales(filters):
    # type: (Filters) -> Tuple[str, Tuple[Any, ...]]
    params = []  # type: List[Any]
    if filters.channel == "Reseller":
        return """
SELECT TOP (0)
    CAST(NULL AS varchar(100)) AS country,
    CAST(NULL AS varchar(100)) AS state_province,
    CAST(NULL AS varchar(100)) AS city,
    CAST(0 AS decimal(18, 2)) AS sales_amount,
    CAST(0 AS int) AS customer_count,
    CAST(0 AS int) AS order_count;
""", tuple(params)

    date_clause = _date_clause("d", filters, params)
    product_clause = _product_clause("p", filters, params)
    country_value_clause = "1=1"
    if filters.country:
        params.append(filters.country)
        country_value_clause = "g.EnglishCountryRegionName = %s"
    sql = """
SELECT TOP (100)
    g.EnglishCountryRegionName AS country,
    g.StateProvinceName AS state_province,
    g.City AS city,
    CAST(SUM(fis.SalesAmount) AS decimal(18, 2)) AS sales_amount,
    COUNT(DISTINCT fis.CustomerKey) AS customer_count,
    COUNT(DISTINCT fis.SalesOrderNumber) AS order_count
FROM dbo.FactInternetSales fis
JOIN dbo.DimDate d ON fis.OrderDateKey = d.DateKey
JOIN dbo.DimProduct p ON fis.ProductKey = p.ProductKey
JOIN dbo.DimCustomer c ON fis.CustomerKey = c.CustomerKey
JOIN dbo.DimGeography g ON c.GeographyKey = g.GeographyKey
WHERE %s
  AND %s
  AND %s
GROUP BY g.EnglishCountryRegionName, g.StateProvinceName, g.City
ORDER BY sales_amount DESC;
""" % (date_clause, product_clause, country_value_clause)
    return sql, tuple(params)


def build_channels(filters):
    # type: (Filters) -> Tuple[str, Tuple[Any, ...]]
    params = []  # type: List[Any]
    date_clause = _date_clause("d", filters, params)
    product_clause = _product_clause("p", filters, params)
    channel_clause = _channel_clause("us", filters, params)
    country_clause = _country_clause("us", filters, params)
    sql = """
%s,
ChannelAgg AS (
    SELECT
        us.SalesChannel,
        CAST(SUM(us.SalesAmount) AS decimal(18, 2)) AS sales_amount,
        COUNT(DISTINCT us.SalesOrderNumber) AS order_count
    FROM UnifiedSales us
    JOIN dbo.DimDate d ON us.OrderDateKey = d.DateKey
    JOIN dbo.DimProduct p ON us.ProductKey = p.ProductKey
    WHERE %s
      AND %s
      AND %s
      AND %s
    GROUP BY us.SalesChannel
)
SELECT
    SalesChannel AS sales_channel,
    sales_amount,
    order_count,
    CAST(sales_amount / NULLIF(SUM(sales_amount) OVER (), 0) AS decimal(18, 4)) AS sales_ratio,
    CAST(order_count * 1.0 / NULLIF(SUM(order_count) OVER (), 0) AS decimal(18, 4)) AS order_ratio,
    CAST(sales_amount / NULLIF(order_count, 0) AS decimal(18, 2)) AS avg_order_amount
FROM ChannelAgg
ORDER BY sales_amount DESC;
""" % (UNIFIED_SALES_CTE, date_clause, product_clause, channel_clause, country_clause)
    return sql, tuple(params)


def build_filter_options():
    # type: () -> str
    return """
SELECT 'product_line' AS option_type, COALESCE(ProductLine, 'Unknown') AS option_value
FROM dbo.DimProduct
GROUP BY COALESCE(ProductLine, 'Unknown')
UNION ALL
SELECT 'country' AS option_type, EnglishCountryRegionName AS option_value
FROM dbo.DimGeography
WHERE EnglishCountryRegionName IS NOT NULL
GROUP BY EnglishCountryRegionName
UNION ALL
SELECT 'year' AS option_type, CAST(CalendarYear AS varchar(20)) AS option_value
FROM dbo.DimDate
GROUP BY CalendarYear
ORDER BY option_type, option_value;
"""
