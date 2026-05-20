"""Flask API for the K-predict SCI/SIC research workbench."""

from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd
from flask import Flask, jsonify, request

ROOT = Path(__file__).resolve().parents[1]
KRONOS_ROOT = ROOT / "kronos_repo"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(KRONOS_ROOT))

from kp_multifactor.config import TICKERS  # noqa: E402
from kp_multifactor.data_sources import create_reference_tables, load_or_create_prices  # noqa: E402
from kp_multifactor.portfolio import build_report  # noqa: E402
from kp_multifactor.prediction_audit import audit_result_files, summarize_prediction_error, compare_prediction_to_actual  # noqa: E402
from kp_multifactor.research_writer import write_research_notes  # noqa: E402

try:
    from model import Kronos, KronosPredictor, KronosTokenizer  # type: ignore

    KRONOS_AVAILABLE = True
except Exception:
    Kronos = KronosPredictor = KronosTokenizer = None
    KRONOS_AVAILABLE = False


MODEL_CONFIGS = {
    "kronos-mini": {
        "model_id": "NeoQuasar/Kronos-mini",
        "tokenizer_id": "NeoQuasar/Kronos-Tokenizer-2k",
        "context_length": 2048,
        "label": "Kronos mini",
    },
    "kronos-small": {
        "model_id": "NeoQuasar/Kronos-small",
        "tokenizer_id": "NeoQuasar/Kronos-Tokenizer-base",
        "context_length": 512,
        "label": "Kronos small",
    },
    "kronos-base": {
        "model_id": "NeoQuasar/Kronos-base",
        "tokenizer_id": "NeoQuasar/Kronos-Tokenizer-base",
        "context_length": 512,
        "label": "Kronos base",
    },
}

LOADED_MODEL: dict[str, Any] = {}


def create_app() -> Flask:
    app = Flask(__name__)

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

    @app.route("/api/workbench/status", methods=["GET"])
    def status():
        ensure_reference_data()
        report = ensure_multifactor_report()
        latest_runs = read_csv_records(ROOT / "outputs/ui_research_log/prediction_runs.csv", limit=8)
        return jsonify(
            {
                "tickers": list(TICKERS),
                "models": [
                    {"id": key, **value, "available": KRONOS_AVAILABLE}
                    for key, value in MODEL_CONFIGS.items()
                ],
                "kronosAvailable": KRONOS_AVAILABLE,
                "macro": report.get("macro_holding_model", {}),
                "ranking": report.get("multifactor_ranking", []),
                "documentPortfolio": report.get("document_portfolio", {}),
                "latestRuns": latest_runs,
                "generatedAt": datetime.now().isoformat(),
            }
        )

    @app.route("/api/workbench/files", methods=["GET"])
    def files():
        return jsonify(build_file_catalog())

    @app.route("/api/workbench/research-log", methods=["GET"])
    def research_log():
        output_dir = ROOT / "outputs/ui_research_log"
        notes_path = output_dir / "research_notes.md"
        runs = read_csv_records(output_dir / "prediction_runs.csv", limit=100)
        points = read_csv_records(output_dir / "prediction_points.csv", limit=200)
        report = ensure_multifactor_report()
        return jsonify(
            {
                "runs": runs,
                "pointsPreview": points,
                "notes": notes_path.read_text(encoding="utf-8") if notes_path.exists() else "",
                "multifactor": report,
            }
        )

    @app.route("/api/workbench/audit", methods=["POST", "OPTIONS"])
    def audit():
        if request.method == "OPTIONS":
            return ("", 204)
        data = request.get_json(silent=True) or {}
        results_dir = resolve_safe_path(data.get("results_dir") or "outputs/ui_predictions")
        output_dir = resolve_safe_path(data.get("output_dir") or "outputs/ui_research_log")
        paths = sorted(results_dir.glob("**/*.json"))
        runs, points = audit_result_files(paths)
        output_dir.mkdir(parents=True, exist_ok=True)
        runs_path = output_dir / "prediction_runs.csv"
        points_path = output_dir / "prediction_points.csv"
        runs.to_csv(runs_path, index=False)
        points.to_csv(points_path, index=False)
        notes = write_research_notes(runs, ensure_multifactor_report(), output_dir / "research_notes.md")
        return jsonify(
            {
                "success": True,
                "runCount": len(runs),
                "pointCount": len(points),
                "runsPath": str(runs_path),
                "pointsPath": str(points_path),
                "notes": notes,
            }
        )

    @app.route("/api/workbench/predict", methods=["POST", "OPTIONS"])
    def predict():
        if request.method == "OPTIONS":
            return ("", 204)
        if not KRONOS_AVAILABLE:
            return jsonify({"error": "Kronos model package is not available in this environment."}), 500
        data = request.get_json(silent=True) or {}
        ticker = str(data.get("ticker", "ADBE")).upper()
        model_key = str(data.get("model", "kronos-base"))
        lookback = int(data.get("lookback", 400))
        pred_len = int(data.get("pred_len", 30))
        temperature = float(data.get("temperature", 1.0))
        top_p = float(data.get("top_p", 0.9))
        sample_count = int(data.get("sample_count", 1))
        if ticker not in TICKERS:
            return jsonify({"error": f"Unsupported ticker: {ticker}"}), 400
        if model_key not in MODEL_CONFIGS:
            return jsonify({"error": f"Unsupported model: {model_key}"}), 400

        price_path = ROOT / f"data/kronos_daily/{ticker}_daily.csv"
        if not price_path.exists():
            ensure_reference_data()
        if not price_path.exists():
            return jsonify({"error": f"Missing price file: {price_path}"}), 400

        result_path, summary = run_kronos_prediction(
            ticker=ticker,
            model_key=model_key,
            price_path=price_path,
            lookback=lookback,
            pred_len=pred_len,
            temperature=temperature,
            top_p=top_p,
            sample_count=sample_count,
        )
        audit_dir = ROOT / "outputs/ui_research_log"
        audit_paths = sorted((ROOT / "outputs/ui_predictions").glob("**/*.json"))
        runs, points = audit_result_files(audit_paths)
        audit_dir.mkdir(parents=True, exist_ok=True)
        runs.to_csv(audit_dir / "prediction_runs.csv", index=False)
        points.to_csv(audit_dir / "prediction_points.csv", index=False)
        notes = write_research_notes(runs, ensure_multifactor_report(), audit_dir / "research_notes.md")
        return jsonify(
            {
                "success": True,
                "resultPath": str(result_path),
                "summary": clean_json(summary),
                "notes": notes,
            }
        )

    return app


def ensure_reference_data() -> None:
    if not (ROOT / "data/prices.csv").exists():
        load_or_create_prices(ROOT / "data/prices.csv", prefer_live=False)
    required = ["fundamentals.csv", "esg.csv", "macro.csv", "portfolio.csv"]
    if not all((ROOT / "data" / name).exists() for name in required):
        create_reference_tables(ROOT / "data")


def ensure_multifactor_report() -> dict[str, Any]:
    ensure_reference_data()
    report_path = ROOT / "outputs/multifactor_report.json"
    if report_path.exists():
        return json.loads(report_path.read_text(encoding="utf-8"))
    report = build_report(
        prices=pd.read_csv(ROOT / "data/prices.csv", parse_dates=["timestamp"]),
        fundamentals=pd.read_csv(ROOT / "data/fundamentals.csv", parse_dates=["date"]),
        esg=pd.read_csv(ROOT / "data/esg.csv", parse_dates=["date"]),
        macro=pd.read_csv(ROOT / "data/macro.csv", parse_dates=["date"]),
        output_path=report_path,
    )
    return report


def load_predictor(model_key: str):
    if LOADED_MODEL.get("key") == model_key:
        return LOADED_MODEL["predictor"]
    config = MODEL_CONFIGS[model_key]
    tokenizer = KronosTokenizer.from_pretrained(config["tokenizer_id"])
    model = Kronos.from_pretrained(config["model_id"])
    predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=config["context_length"])
    LOADED_MODEL.clear()
    LOADED_MODEL.update({"key": model_key, "predictor": predictor})
    return predictor


def run_kronos_prediction(
    ticker: str,
    model_key: str,
    price_path: Path,
    lookback: int,
    pred_len: int,
    temperature: float,
    top_p: float,
    sample_count: int,
) -> tuple[Path, dict[str, Any]]:
    df = pd.read_csv(price_path)
    df["timestamps"] = pd.to_datetime(df["timestamps"])
    if len(df) < lookback + pred_len:
        raise ValueError(f"Need at least {lookback + pred_len} rows, got {len(df)}")

    start = len(df) - 120 - lookback if len(df) >= lookback + pred_len + 120 else len(df) - lookback - pred_len
    start = max(0, start)
    split = start + lookback
    hist = df.iloc[start:split].copy().reset_index(drop=True)
    actual = df.iloc[split : split + pred_len].copy().reset_index(drop=True)
    predictor = load_predictor(model_key)
    pred = predictor.predict(
        df=hist[["open", "high", "low", "close", "volume", "amount"]],
        x_timestamp=hist["timestamps"],
        y_timestamp=actual["timestamps"],
        pred_len=pred_len,
        T=temperature,
        top_p=top_p,
        sample_count=sample_count,
        verbose=False,
    ).reset_index(drop=True)

    pred_rows = frame_rows(pred, actual["timestamps"])
    actual_rows = frame_rows(actual[["open", "high", "low", "close", "volume", "amount"]], actual["timestamps"])
    payload = {
        "timestamp": datetime.now().isoformat(),
        "file_path": str(price_path),
        "prediction_type": f"{model_key} workbench holdout prediction",
        "prediction_params": {
            "lookback": lookback,
            "pred_len": pred_len,
            "temperature": temperature,
            "top_p": top_p,
            "sample_count": sample_count,
            "start_date": hist["timestamps"].iloc[0].isoformat(),
            "model": model_key,
        },
        "input_data_summary": {
            "rows": len(hist),
            "columns": ["open", "high", "low", "close", "volume", "amount"],
            "price_range": {
                col: {"min": float(hist[col].min()), "max": float(hist[col].max())}
                for col in ["open", "high", "low", "close"]
            },
            "last_values": {col: float(hist[col].iloc[-1]) for col in ["open", "high", "low", "close"]},
        },
        "prediction_results": pred_rows,
        "actual_data": actual_rows,
        "analysis": {"note": "Generated by K-predict SCI/SIC workbench."},
    }
    out_dir = ROOT / "outputs/ui_predictions" / model_key
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    points = compare_prediction_to_actual({**payload, "_source_path": str(output_path), "_run_id": output_path.stem})
    summary = summarize_prediction_error(points, payload)
    return output_path, summary


def frame_rows(frame: pd.DataFrame, timestamps: pd.Series) -> list[dict[str, Any]]:
    rows = []
    for idx, row in frame.reset_index(drop=True).iterrows():
        rows.append(
            {
                "timestamp": pd.Timestamp(timestamps.iloc[idx]).isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "amount": float(row["amount"]),
            }
        )
    return rows


def build_file_catalog() -> list[dict[str, Any]]:
    specs = [
        ("data/prices.csv", "Unified price table", "Core OHLCV data for portfolio and risk analytics", True),
        ("data/fundamentals.csv", "Fundamental factors", "ROE, growth, valuation, FCFF, and Z-score", True),
        ("data/esg.csv", "ESG factors", "MSCI, Sustainalytics, and governance notes", True),
        ("data/macro.csv", "Macro model", "Fed, GDP, unemployment, VIX, flows, and 77% holding score", True),
        ("data/portfolio.csv", "Portfolio weights", "Document target weights for LLY, ADBE, and GOOGL", True),
        ("data/kronos_daily", "Kronos input files", "One Kronos-ready CSV per stock", True),
        ("outputs/ui_predictions", "Workbench predictions", "Saved Kronos JSON predictions generated from the UI", True),
        ("outputs/ui_research_log", "Research log", "Prediction errors and AI-readable notes for reports", True),
        ("outputs/multifactor_report.json", "Multi-factor report", "Macro, portfolio, ranking, and audit summary", True),
    ]
    catalog = []
    for rel_path, label, purpose, report_ready in specs:
        path = ROOT / rel_path
        catalog.append(
            {
                "path": rel_path,
                "label": label,
                "purpose": purpose,
                "exists": path.exists(),
                "updatedAt": datetime.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else None,
                "size": path_size(path) if path.exists() else None,
                "generatedBy": "K-predict workbench",
                "reportReady": report_ready,
                "dataSource": "demo/synthetic + Kronos output" if rel_path.startswith(("data", "outputs")) else "local",
            }
        )
    return catalog


def read_csv_records(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return pd.read_csv(path).tail(limit).replace({float("nan"): None}).to_dict(orient="records")


def resolve_safe_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    if ROOT not in path.parents and path != ROOT:
        raise ValueError("Path must stay inside project root")
    return path


def path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(child.stat().st_size for child in path.glob("**/*") if child.is_file())


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7080, debug=True)
