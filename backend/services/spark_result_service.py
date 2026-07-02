import json
import os
from datetime import datetime
from typing import Any, Dict, Optional


RESULT_FILENAMES = {
    "kpis": "kpis.json",
    "trend": "trend.json",
    "top_products": "top_products.json",
    "channels": "channels.json",
    "geo_sales": "geo_sales.json",
    "alerts": "alerts.json",
}


def get_project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_result_dir():
    return os.path.abspath(
        os.getenv("SPARK_RESULT_DIR", os.path.join(get_project_root(), "output", "spark_result"))
    )


def get_result_path(name):
    filename = RESULT_FILENAMES.get(name, name)
    return os.path.join(get_result_dir(), filename)


def read_json_result(name):
    path = get_result_path(name)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, dict):
        payload.setdefault("source", "spark")
        payload.setdefault("result_file", os.path.basename(path))
    return payload


def write_json_result(name, payload):
    os.makedirs(get_result_dir(), exist_ok=True)
    path = get_result_path(name)
    data = dict(payload)
    data.setdefault("source", "spark")
    data.setdefault("generated_at", datetime.utcnow().isoformat(timespec="seconds") + "Z")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def missing_result_response(name):
    return {
        "status": "spark_result_missing",
        "message": "Spark result file is missing. Run the Spark job first.",
        "result": name,
        "expected_file": get_result_path(name),
        "spark_submit": (
            "/export/server/spark/bin/spark-submit --master spark://node1:7077 "
            "--name EnterpriseSalesPanoramaSpark --jars /export/server/spark/jars/mssql-jdbc.jar "
            "backend/spark_jobs/sales_spark_job.py"
        ),
    }


def read_text_result(filename):
    path = os.path.join(get_result_dir(), filename)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text_result(filename, content):
    os.makedirs(get_result_dir(), exist_ok=True)
    path = os.path.join(get_result_dir(), filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def result_metadata() -> Dict[str, Optional[Dict[str, Any]]]:
    metadata = {}
    for name, filename in RESULT_FILENAMES.items():
        path = os.path.join(get_result_dir(), filename)
        if os.path.isfile(path):
            stat = os.stat(path)
            metadata[name] = {
                "path": path,
                "size": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        else:
            metadata[name] = None
    return metadata
