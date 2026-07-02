import os


def env_bool(name, default=True):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_sqlserver_jdbc_config():
    host = os.getenv("SQLSERVER_HOST", os.getenv("DB_SERVER", "119.29.239.123"))
    port = os.getenv("SQLSERVER_PORT", "1433")
    database = os.getenv("SQLSERVER_DATABASE", os.getenv("DB_DATABASE", "AdventureWorksDW"))
    trust_certificate = env_bool("SQLSERVER_TRUST_CERTIFICATE", True)
    encrypt = env_bool("SQLSERVER_ENCRYPT", True)
    url = (
        "jdbc:sqlserver://%s:%s;"
        "databaseName=%s;"
        "encrypt=%s;"
        "trustServerCertificate=%s;"
    ) % (
        host,
        port,
        database,
        str(encrypt).lower(),
        str(trust_certificate).lower(),
    )
    return {
        "url": url,
        "user": os.getenv("SQLSERVER_USER", os.getenv("DB_USER", "readonlyuser")),
        "password": os.getenv("SQLSERVER_PASSWORD", os.getenv("DB_PASSWORD", "Bigdata@123")),
        "driver": os.getenv("SQLSERVER_JDBC_DRIVER", "com.microsoft.sqlserver.jdbc.SQLServerDriver"),
        "database": database,
        "host": host,
        "port": port,
    }


def get_output_dir():
    configured = os.getenv("SPARK_RESULT_DIR")
    if configured:
        return os.path.abspath(configured)
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "output", "spark_result")
    )
