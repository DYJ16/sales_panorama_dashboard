import os

from ai.deepseek_v4_report import generate_report
from services.spark_result_service import read_text_result


def get_ai_report():
    content = read_text_result("ai_report.txt")
    if content is None:
        return {
            "status": "ai_report_missing",
            "message": "AI report is missing. Generate it from Spark results first.",
            "report": "",
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        }
    return {
        "status": "ok",
        "report": content,
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    }


def generate_ai_report():
    try:
        result = generate_report()
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            "report": "",
        }
    return {
        "status": "ok",
        "mode": result["mode"],
        "model": result["model"],
        "report": result["report"],
    }
