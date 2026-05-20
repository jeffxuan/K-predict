"""Shared configuration for the investment-contest prototype."""

from __future__ import annotations

from dataclasses import dataclass


TICKERS = ("ADBE", "LLY", "GOOGL")
START_DATE = "2019-01-01"
END_DATE = "2025-10-31"

# Portfolio reported in the Tencent Docs investment plan.
DOCUMENT_WEIGHTS = {
    "LLY": 0.4608,
    "ADBE": 0.2050,
    "GOOGL": 0.3342,
}

MACRO_DIMENSIONS = {
    "policy": {"weight": 0.30, "score": 75.0},
    "fundamental": {"weight": 0.40, "score": 80.0},
    "capital": {"weight": 0.20, "score": 70.0},
    "black_swan": {"weight": 0.10, "score": 85.0},
}

RISK_FREE_RATE = 0.04


@dataclass(frozen=True)
class DataPaths:
    prices: str = "data/prices.csv"
    fundamentals: str = "data/fundamentals.csv"
    esg: str = "data/esg.csv"
    macro: str = "data/macro.csv"
    portfolio: str = "data/portfolio.csv"
    report: str = "outputs/multifactor_report.json"
