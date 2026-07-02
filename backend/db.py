import datetime
import decimal
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

try:
    import pymssql
except ImportError:
    pymssql = None


DB_SERVER = os.getenv("DB_SERVER", os.getenv("SQLSERVER_HOST", "119.29.239.123"))
DB_DATABASE = os.getenv("DB_DATABASE", os.getenv("SQLSERVER_DATABASE", "AdventureWorksDW"))
DB_USER = os.getenv("DB_USER", os.getenv("SQLSERVER_USER", "readonlyuser"))
DB_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("SQLSERVER_PASSWORD", "Bigdata@123"))
DB_LOGIN_TIMEOUT = int(os.getenv("DB_LOGIN_TIMEOUT", "10"))
DB_QUERY_TIMEOUT = int(os.getenv("DB_QUERY_TIMEOUT", "30"))


def get_db_config():
    return {
        "server": DB_SERVER,
        "database": DB_DATABASE,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "login_timeout": DB_LOGIN_TIMEOUT,
        "timeout": DB_QUERY_TIMEOUT,
    }


@contextmanager
def get_connection():
    if pymssql is None:
        raise RuntimeError(
            "pymssql is not installed. SQL Server direct fallback is unavailable; "
            "run the Spark job first or install pymssql separately."
        )
    config = get_db_config()
    conn = pymssql.connect(**config)
    try:
        yield conn
    finally:
        conn.close()


def _format_value(value):
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def _format_row(row):
    return dict((key, _format_value(value)) for key, value in row.items())


def fetch_all(sql, params=()):
    # type: (str, Iterable[Any]) -> List[Dict[str, Any]]
    with get_connection() as conn:
        cur = conn.cursor(as_dict=True)
        cur.execute(sql, tuple(params))
        return [_format_row(row) for row in cur.fetchall()]


def fetch_one(sql, params=()):
    # type: (str, Iterable[Any]) -> Optional[Dict[str, Any]]
    rows = fetch_all(sql, params)
    return rows[0] if rows else None
