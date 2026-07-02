import json
import os
import sys

import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from ai.prompt_templates import SYSTEM_PROMPT, build_user_prompt
from services.spark_result_service import read_json_result, write_text_result


RESULT_KEYS = ["kpis", "trend", "top_products", "channels", "geo_sales", "alerts"]
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_API_KEY = ""


def load_analysis_context():
    context = {}
    for key in RESULT_KEYS:
        context[key] = read_json_result(key) or {"status": "spark_result_missing", "items": []}
    return context


def generate_report():
    model = os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
    api_key = os.getenv("DEEPSEEK_API_KEY", DEFAULT_DEEPSEEK_API_KEY)
    context = load_analysis_context()

    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required to generate a real DeepSeek V4 report.")

    base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL).rstrip("/")
    timeout = float(os.getenv("DEEPSEEK_TIMEOUT", "60"))
    response = requests.post(
        "%s/chat/completions" % base_url,
        headers={
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(context)},
            ],
            "temperature": float(os.getenv("DEEPSEEK_TEMPERATURE", "0.3")),
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    report = payload["choices"][0]["message"]["content"]
    write_text_result("ai_report.txt", report)
    return {"mode": "deepseek", "model": model, "report": report}


def main():
    result = generate_report()
    print(json.dumps({"mode": result["mode"], "model": result["model"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
