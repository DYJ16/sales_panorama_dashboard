from spark_config import get_sqlserver_jdbc_config


CORE_TABLES = {
    "internet_sales": "dbo.FactInternetSales",
    "reseller_sales": "dbo.FactResellerSales",
    "date": "dbo.DimDate",
    "product": "dbo.DimProduct",
    "customer": "dbo.DimCustomer",
    "geography": "dbo.DimGeography",
}


def read_table(spark, table_name):
    config = get_sqlserver_jdbc_config()
    return (
        spark.read.format("jdbc")
        .option("url", config["url"])
        .option("dbtable", table_name)
        .option("user", config["user"])
        .option("password", config["password"])
        .option("driver", config["driver"])
        .load()
    )


def read_core_tables(spark):
    return {name: read_table(spark, table) for name, table in CORE_TABLES.items()}
