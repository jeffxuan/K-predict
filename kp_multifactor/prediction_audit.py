"""Audit Kronos prediction JSON files against actual outcomes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import TICKERS


PRICE_COLUMNS = ("open", "high", "low", "close", "volume", "amount")


def load_kronos_result(path: str | Path) -> dict[str, Any]:
    """Load a Kronos WebUI prediction result and attach source metadata."""

    source_path = Path(path)
    result = json.loads(source_path.read_text(encoding="utf-8"))
    result["_source_path"] = str(source_path)
    result["_run_id"] = make_run_id(source_path, result)
    return result


def make_run_id(path: str | Path, result: dict[str, Any]) -> str:
    """Create a stable short run id from file path and run timestamp."""

    raw = f"{Path(path).name}|{result.get('timestamp', '')}|{result.get('file_path', '')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def infer_ticker_from_file_path(file_path: str | None) -> str:
    """Infer ADBE/LLY/GOOGL from a Kronos result input path."""

    if not file_path:
        return "UNKNOWN"
    upper = Path(file_path).name.upper()
    for ticker in TICKERS:
        if ticker in upper:
            return ticker
    if "GOOG" in upper:
        return "GOOGL"
    return "UNKNOWN"


def _records_to_frame(records: list[dict[str, Any]], prefix: str) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    if "timestamp" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    rename = {column: f"{prefix}_{column}" for column in PRICE_COLUMNS if column in frame.columns}
    return frame.rename(columns=rename)


def compare_prediction_to_actual(result: dict[str, Any]) -> pd.DataFrame:
    """Return point-level prediction errors.

    If actual data is missing, the returned rows are still useful as pending
    predictions and all actual/error fields remain null.
    """

    run_id = result.get("_run_id") or make_run_id(result.get("_source_path", "unknown"), result)
    ticker = infer_ticker_from_file_path(result.get("file_path"))
    pred = _records_to_frame(result.get("prediction_results") or [], "pred")
    actual = _records_to_frame(result.get("actual_data") or [], "actual")

    if pred.empty:
        return pd.DataFrame()

    if actual.empty:
        points = pred.copy()
        for column in PRICE_COLUMNS:
            points[f"actual_{column}"] = np.nan
    else:
        points = pred.merge(actual, on="timestamp", how="left")

    points.insert(0, "run_id", run_id)
    points.insert(1, "ticker", ticker)

    for column in PRICE_COLUMNS:
        pred_col = f"pred_{column}"
        actual_col = f"actual_{column}"
        if pred_col in points.columns and actual_col in points.columns:
            points[f"{column}_error"] = points[pred_col] - points[actual_col]
            denominator = points[actual_col].replace(0, np.nan).abs()
            points[f"{column}_error_pct"] = points[f"{column}_error"] / denominator

    if {"pred_close", "actual_close"}.issubset(points.columns):
        pred_delta = points["pred_close"].diff()
        actual_delta = points["actual_close"].diff()
        points["direction_correct"] = np.where(
            pred_delta.notna() & actual_delta.notna(),
            np.sign(pred_delta) == np.sign(actual_delta),
            np.nan,
        )
    else:
        points["direction_correct"] = np.nan

    return points


def summarize_prediction_error(points: pd.DataFrame, result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Summarize one point-level audit DataFrame."""

    if points.empty:
        return {
            "status": "empty_prediction",
            "point_count": 0,
        }

    result = result or {}
    params = result.get("prediction_params") or {}
    input_summary = result.get("input_data_summary") or {}
    last_values = input_summary.get("last_values") or {}
    has_actuals = points.get("actual_close", pd.Series(dtype=float)).notna().any()
    status = "evaluated" if has_actuals else "pending_actuals"

    first_pred_close = float(points["pred_close"].iloc[0]) if "pred_close" in points else np.nan
    last_pred_close = float(points["pred_close"].iloc[-1]) if "pred_close" in points else np.nan
    base_close = float(last_values.get("close", first_pred_close))
    predicted_return = _safe_return(last_pred_close, base_close)

    summary: dict[str, Any] = {
        "run_id": points["run_id"].iloc[0],
        "ticker": points["ticker"].iloc[0],
        "status": status,
        "model": _infer_model_label(result),
        "timestamp": result.get("timestamp"),
        "file_path": result.get("file_path"),
        "lookback": params.get("lookback"),
        "pred_len": params.get("pred_len", len(points)),
        "temperature": params.get("temperature"),
        "top_p": params.get("top_p"),
        "sample_count": params.get("sample_count"),
        "point_count": int(len(points)),
        "base_close": base_close,
        "predicted_return": predicted_return,
    }

    if has_actuals:
        actual_close = points["actual_close"]
        pred_close = points["pred_close"]
        close_error = pred_close - actual_close
        actual_return = _safe_return(float(actual_close.iloc[-1]), base_close)
        summary.update(
            {
                "close_mae": float(close_error.abs().mean()),
                "close_mape": float((close_error.abs() / actual_close.replace(0, np.nan).abs()).mean()),
                "max_close_deviation_pct": float(
                    (close_error.abs() / actual_close.replace(0, np.nan).abs()).max()
                ),
                "direction_accuracy": _mean_bool(points["direction_correct"]),
                "actual_return": actual_return,
                "return_error": predicted_return - actual_return,
                "volume_mape": _mape(points.get("pred_volume"), points.get("actual_volume")),
            }
        )
    else:
        summary.update(
            {
                "close_mae": np.nan,
                "close_mape": np.nan,
                "max_close_deviation_pct": np.nan,
                "direction_accuracy": np.nan,
                "actual_return": np.nan,
                "return_error": np.nan,
                "volume_mape": np.nan,
            }
        )

    return summary


def audit_result_files(paths: list[str | Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Audit many Kronos result files into run-level and point-level tables."""

    run_rows: list[dict[str, Any]] = []
    point_frames: list[pd.DataFrame] = []
    for path in paths:
        result = load_kronos_result(path)
        points = compare_prediction_to_actual(result)
        if points.empty:
            run_rows.append(summarize_prediction_error(points, result))
            continue
        run_rows.append(summarize_prediction_error(points, result))
        point_frames.append(points)

    runs = pd.DataFrame(run_rows)
    points = pd.concat(point_frames, ignore_index=True) if point_frames else pd.DataFrame()
    return runs, points


def _safe_return(end: float, start: float) -> float:
    if not np.isfinite(end) or not np.isfinite(start) or start == 0:
        return float("nan")
    return float(end / start - 1)


def _mape(predicted: pd.Series | None, actual: pd.Series | None) -> float:
    if predicted is None or actual is None:
        return float("nan")
    denominator = actual.replace(0, np.nan).abs()
    return float(((predicted - actual).abs() / denominator).mean())


def _mean_bool(series: pd.Series) -> float:
    clean = series.dropna()
    if clean.empty:
        return float("nan")
    return float(clean.astype(bool).mean())


def _infer_model_label(result: dict[str, Any]) -> str:
    prediction_type = str(result.get("prediction_type") or "")
    if "mini" in prediction_type.lower():
        return "kronos-mini"
    if "small" in prediction_type.lower():
        return "kronos-small"
    if "base" in prediction_type.lower():
        return "kronos-base"
    return "kronos"
