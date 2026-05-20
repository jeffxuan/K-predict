"""Scoring helpers for macro, fundamental, and ESG factors."""

from __future__ import annotations

import pandas as pd

from .config import MACRO_DIMENSIONS


MSCI_SCORE = {
    "AAA": 100.0,
    "AA": 90.0,
    "A": 78.0,
    "BBB": 64.0,
    "BB": 48.0,
    "B": 32.0,
    "CCC": 16.0,
}


def macro_holding_score(macro: pd.DataFrame) -> dict[str, float]:
    row = macro.iloc[-1]
    score = (
        row["policy_score"] * MACRO_DIMENSIONS["policy"]["weight"]
        + row["fundamental_score"] * MACRO_DIMENSIONS["fundamental"]["weight"]
        + row["capital_score"] * MACRO_DIMENSIONS["capital"]["weight"]
        + row["black_swan_score"] * MACRO_DIMENSIONS["black_swan"]["weight"]
    )
    return {
        "score": round(float(score), 4),
        "suggested_equity_exposure": round(float(score) / 100.0, 4),
    }


def _rank_percentile(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    values = series.rank(pct=True, ascending=not higher_is_better)
    return values.fillna(values.mean()).fillna(0.5) * 100


def score_fundamentals(fundamentals: pd.DataFrame) -> pd.DataFrame:
    df = fundamentals.copy()
    df["profitability_score"] = _rank_percentile(df["roe"], True)
    df["growth_score"] = (
        _rank_percentile(df["revenue_growth"], True) * 0.45
        + _rank_percentile(df["net_income_growth"], True) * 0.55
    )
    df["valuation_score"] = _rank_percentile(df["peg"], False) * 0.60 + _rank_percentile(df["pe"], False) * 0.40
    df["financial_health_score"] = _rank_percentile(df["z_score"], True)
    df["fundamental_score"] = (
        df["profitability_score"] * 0.30
        + df["growth_score"] * 0.25
        + df["valuation_score"] * 0.25
        + df["financial_health_score"] * 0.20
    )
    return df


def score_esg(esg: pd.DataFrame) -> pd.DataFrame:
    df = esg.copy()
    df["msci_score"] = df["msci_rating"].map(MSCI_SCORE).fillna(50.0)
    df["sustainalytics_component"] = (100 - df["sustainalytics_score"] * 3).clip(lower=0, upper=100)
    df["esg_score"] = df["msci_score"] * 0.55 + df["sustainalytics_component"] * 0.45
    return df


def combine_multifactor_scores(fundamentals: pd.DataFrame, esg: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    scored_fundamentals = score_fundamentals(fundamentals)
    scored_esg = score_esg(esg)
    macro_score = macro_holding_score(macro)["score"]
    combined = scored_fundamentals.merge(
        scored_esg[["ticker", "msci_rating", "sustainalytics_score", "esg_score", "governance_risk_note"]],
        on="ticker",
        how="left",
    )
    combined["macro_score"] = macro_score
    combined["combined_score"] = (
        combined["fundamental_score"] * 0.50
        + combined["esg_score"] * 0.25
        + combined["macro_score"] * 0.15
        + combined["financial_health_score"] * 0.10
    )
    return combined.sort_values("combined_score", ascending=False).reset_index(drop=True)
