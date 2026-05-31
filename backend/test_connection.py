import os

from db import fetch_one


def main() -> None:
    row = fetch_one(
        """
        SELECT
            DB_NAME() AS database_name,
            (SELECT COUNT(*) FROM dbo.FactInternetSales) AS internet_sales_rows,
            (SELECT COUNT(*) FROM dbo.FactResellerSales) AS reseller_sales_rows
        """
    )
    print(row)


if __name__ == "__main__":
    main()
