#!/usr/bin/env python3
"""
HTTP сервер для запуска парсера Profi
Слушает на порту 8765

Endpoints:
  GET/POST /parse       - Парсинг одного прайса (Астрахань по умолчанию)
  GET/POST /parse/all   - Парсинг всех прайс-листов (37 точек)
  GET /health           - Проверка состояния
"""
import subprocess
import sys
from flask import Flask, jsonify, request

app = Flask(__name__)

PARSER_SCRIPT = "/opt/parsers/profi/parse_profi.py"


@app.route("/parse", methods=["GET", "POST"])
def parse():
    """Запустить парсер для одного прайса"""
    try:
        # Получаем опциональные параметры
        url = request.args.get("url")
        city = request.args.get("city")
        shop = request.args.get("shop")

        cmd = ["python3", PARSER_SCRIPT]
        if url:
            cmd.extend(["--url", url])
        if city:
            cmd.extend(["--city", city])
        if shop:
            cmd.extend(["--shop", shop])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        return jsonify({
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "error": "Timeout after 300 seconds"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/parse/all", methods=["GET", "POST"])
def parse_all():
    """Запустить парсер для всех прайс-листов"""
    try:
        result = subprocess.run(
            ["python3", PARSER_SCRIPT, "--all"],
            capture_output=True,
            text=True,
            timeout=1800  # 30 минут для всех прайсов
        )

        return jsonify({
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "error": "Timeout after 1800 seconds"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8765)
