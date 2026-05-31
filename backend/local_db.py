import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
import pymssql
from db import get_db_config

DB_PATH = os.path.join(os.path.dirname(__file__), "sales_crud.db")


@contextmanager
def get_local_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def sync_and_init_db():
    # 1. 创建 products 表
    with get_local_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_key INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                product_line TEXT,
                color TEXT,
                size TEXT,
                list_price REAL DEFAULT 0.0,
                model_name TEXT,
                sales_amount REAL DEFAULT 0.0,
                order_count INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deleted_products (
                product_key INTEGER PRIMARY KEY
            )
            """
        )
        conn.commit()

        # 2. 检查是否有数据
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        count = cursor.fetchone()[0]
        if count > 0:
            return  # 已经有数据了，不再同步

        # 3. 尝试从远程 SQL Server 同步
        remote_products = []
        try:
            config = get_db_config()
            # 缩短同步时的连接超时，避免无网络时卡住很久
            sync_config = config.copy()
            sync_config["login_timeout"] = 3
            sync_config["timeout"] = 5
            
            with pymssql.connect(**sync_config) as r_conn:
                r_cur = r_conn.cursor(as_dict=True)
                sql = """
                SELECT DISTINCT TOP 30
                    p.ProductKey AS product_key,
                    p.EnglishProductName AS product_name,
                    COALESCE(p.ProductLine, 'Unknown') AS product_line,
                    COALESCE(p.Color, 'Unknown') AS color,
                    COALESCE(p.Size, 'Unknown') AS size,
                    COALESCE(p.ListPrice, 0.0) AS list_price,
                    COALESCE(p.ModelName, 'Unknown') AS model_name
                FROM dbo.DimProduct p
                WHERE p.EnglishProductName IS NOT NULL
                ORDER BY p.ProductKey DESC;
                """
                r_cur.execute(sql)
                rows = r_cur.fetchall()
                for row in rows:
                    # 为模拟真实的销售数据，给予一个随机或计算出的 sales_amount 和 order_count
                    pk = row.get("product_key", 100)
                    import random
                    random.seed(pk)
                    sales = round(random.uniform(50000.0, 5000000.0), 2)
                    orders = random.randint(100, 3000)
                    remote_products.append((
                        pk,
                        row.get("product_name"),
                        row.get("product_line"),
                        row.get("color"),
                        row.get("size"),
                        float(row.get("list_price") or 0.0),
                        row.get("model_name"),
                        sales,
                        orders
                    ))
        except Exception as e:
            print(f"Failed to sync products from SQL Server: {e}. Fallback to mock seeding.")

        # 4. 如果远程拉取失败或没拉到，使用内置 Mock 种子数据
        if not remote_products:
            mock_data = [
                ("Mountain-100 Silver, 38", "M", "Silver", "38", 3399.99, "Mountain-100", 5400000.0, 1200),
                ("Road-150 Red, 56", "R", "Red", "56", 3578.27, "Road-150", 4200000.0, 980),
                ("Mountain-200 Black, 42", "M", "Black", "42", 2294.99, "Mountain-200", 3600000.0, 850),
                ("Road-250 Black, 44", "R", "Black", "44", 2443.35, "Road-250", 2900000.0, 710),
                ("Touring-1000 Yellow, 46", "T", "Yellow", "46", 2384.07, "Touring-1000", 2400000.0, 590),
                ("Mountain-200 Silver, 46", "M", "Silver", "46", 2319.99, "Mountain-200", 2100000.0, 520),
                ("Road-350-W Yellow, 48", "R", "Yellow", "48", 1700.99, "Road-350", 1850000.0, 460),
                ("HL Mountain Frame - Silver, 44", "M", "Silver", "44", 1364.50, "HL Mountain Frame", 1500000.0, 390),
                ("Road-550-W Yellow, 38", "R", "Yellow", "38", 1120.49, "Road-550", 1300000.0, 340),
                ("Sport-100 Helmet, Red", "S", "Red", "Size S", 34.99, "Sport-100", 1100000.0, 3100),
            ]
            for index, mock in enumerate(mock_data):
                remote_products.append((1000 + index, *mock))

        # 5. 写入 SQLite
        conn.executemany(
            """
            INSERT INTO products (product_key, product_name, product_line, color, size, list_price, model_name, sales_amount, order_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            remote_products
        )
        conn.commit()


def get_products(name: Optional[str] = None, product_line: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM products WHERE 1=1"
    params = []
    if name:
        sql += " AND product_name LIKE ?"
        params.append(f"%{name}%")
    if product_line:
        sql += " AND product_line = ?"
        params.append(product_line)
    
    # 按照 product_key 倒序，新增加的在上面
    sql += " ORDER BY product_key DESC"

    with get_local_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def get_product(product_key: int) -> Optional[Dict[str, Any]]:
    with get_local_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE product_key = ?", (product_key,))
        row = cursor.fetchone()
        return dict(row) if row else None


def add_product(
    product_name: str,
    product_line: Optional[str],
    color: Optional[str],
    size: Optional[str],
    list_price: float,
    model_name: Optional[str],
    sales_amount: float = 0.0,
    order_count: int = 0
) -> int:
    with get_local_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO products (product_name, product_line, color, size, list_price, model_name, sales_amount, order_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (product_name, product_line, color, size, list_price, model_name, sales_amount, order_count)
        )
        conn.commit()
        return cursor.lastrowid


def update_product(
    product_key: int,
    product_name: str,
    product_line: Optional[str],
    color: Optional[str],
    size: Optional[str],
    list_price: float,
    model_name: Optional[str]
) -> bool:
    with get_local_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE products
            SET product_name = ?, product_line = ?, color = ?, size = ?, list_price = ?, model_name = ?
            WHERE product_key = ?
            """,
            (product_name, product_line, color, size, list_price, model_name, product_key)
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_product(product_key: int) -> bool:
    with get_local_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE product_key = ?", (product_key,))
        success = cursor.rowcount > 0
        if success:
            cursor.execute("INSERT OR IGNORE INTO deleted_products (product_key) VALUES (?)", (product_key,))
        conn.commit()
        return success


def get_deleted_product_keys() -> List[int]:
    with get_local_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT product_key FROM deleted_products")
        return [row[0] for row in cursor.fetchall()]
