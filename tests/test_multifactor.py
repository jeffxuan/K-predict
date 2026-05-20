from __future__ import annotations

import pandas as pd

from kp_multifactor.data_sources import generate_demo_prices
from kp_multifactor.factors import macro_holding_score
from kp_multifactor.prediction_audit import compare_prediction_to_actual, summarize_prediction_error
from kp_multifactor.portfolio import daily_returns, performance_metrics, portfolio_return_series
from kp_multifactor.research_writer import write_research_notes


def test_macro_holding_score_matches_document_value() -> None:
    macro = pd.DataFrame(
        [
            {
                "policy_score": 75.0,
                "fundamental_score": 80.0,
                "capital_score": 70.0,
                "black_swan_score": 85.0,
            }
        ]
    )
    result = macro_holding_score(macro)
    assert result["score"] == 77.0
    assert result["suggested_equity_exposure"] == 0.77


def test_demo_prices_support_portfolio_metrics() -> None:
    prices = generate_demo_prices()
    returns = daily_returns(prices)
    weights = {"ADBE": 0.2050, "LLY": 0.4608, "GOOGL": 0.3342}
    series = portfolio_return_series(returns, weights)
    metrics = performance_metrics(series)
    assert len(prices) > 1000
    assert set(returns.columns) == {"ADBE", "LLY", "GOOGL"}
    assert metrics["annual_volatility"] > 0


def test_prediction_audit_calculates_errors() -> None:
    result = {
        "_run_id": "abc123",
        "timestamp": "2026-01-01T00:00:00",
        "file_path": "/tmp/ADBE_daily.csv",
        "prediction_params": {"lookback": 2, "pred_len": 3, "temperature": 1.0, "top_p": 0.9, "sample_count": 1},
        "input_data_summary": {"last_values": {"close": 100.0}},
        "prediction_results": [
            {"timestamp": "2026-01-02", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
            {"timestamp": "2026-01-03", "open": 101, "high": 104, "low": 100, "close": 103, "volume": 1100},
            {"timestamp": "2026-01-04", "open": 103, "high": 105, "low": 101, "close": 104, "volume": 1200},
        ],
        "actual_data": [
            {"timestamp": "2026-01-02", "open": 100, "high": 101, "low": 98, "close": 100, "volume": 1000},
            {"timestamp": "2026-01-03", "open": 100, "high": 103, "low": 99, "close": 102, "volume": 1000},
            {"timestamp": "2026-01-04", "open": 102, "high": 104, "low": 100, "close": 103, "volume": 1000},
        ],
    }
    points = compare_prediction_to_actual(result)
    summary = summarize_prediction_error(points, result)
    assert len(points) == 3
    assert summary["ticker"] == "ADBE"
    assert summary["status"] == "evaluated"
    assert summary["close_mae"] == 1.0
    assert summary["direction_accuracy"] == 1.0
    assert round(summary["predicted_return"], 4) == 0.04
    assert round(summary["actual_return"], 4) == 0.03


def test_prediction_audit_handles_missing_actuals() -> None:
    result = {
        "_run_id": "pending1",
        "file_path": "/tmp/LLY_daily.csv",
        "prediction_params": {"pred_len": 1},
        "input_data_summary": {"last_values": {"close": 100.0}},
        "prediction_results": [
            {"timestamp": "2026-01-02", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000}
        ],
    }
    points = compare_prediction_to_actual(result)
    summary = summarize_prediction_error(points, result)
    assert len(points) == 1
    assert summary["ticker"] == "LLY"
    assert summary["status"] == "pending_actuals"
    assert pd.isna(summary["close_mape"])


def test_research_writer_includes_ticker_and_factor_context(tmp_path) -> None:
    runs = pd.DataFrame(
        [
            {
                "run_id": "abc123",
                "ticker": "ADBE",
                "status": "evaluated",
                "close_mape": 0.02,
                "direction_accuracy": 0.75,
                "return_error": 0.01,
                "predicted_return": 0.04,
                "actual_return": 0.03,
            }
        ]
    )
    report = {
        "macro_holding_model": {"score": 77.0, "suggested_equity_exposure": 0.77},
        "document_portfolio": {"weights": {"ADBE": 0.205}},
        "multifactor_ranking": [
            {
                "ticker": "ADBE",
                "industry": "Information Technology",
                "combined_score": 76.36,
                "fundamental_score": 75.0,
                "esg_score": 82.58,
                "msci_rating": "AAA",
                "sustainalytics_score": 12.9,
            }
        ],
    }
    content = write_research_notes(runs, report, tmp_path / "notes.md")
    assert "ADBE" in content
    assert "宏观综合分" in content
    assert "Information Technology" in content
