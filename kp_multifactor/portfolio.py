"""Portfolio analytics and Markowitz-style optimization."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DOCUMENT_WEIGHTS, RISK_FREE_RATE
from .factors import combine_multifactor_scores, macro_holding_score


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    pivot = prices.pivot(index="timestamp", columns="ticker", values="close").sort_index()
    return pivot.pct_change().dropna(how="all")


def portfolio_return_series(returns: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    ordered = returns[list(weights)].dropna()
    weight_vector = np.array([weights[ticker] for ticker in ordered.columns])
    return pd.Series(ordered.to_numpy() @ weight_vector, index=ordered.index, name="portfolio_return")


def performance_metrics(series: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> dict[str, float]:
    clean = series.dropna()
    annual_return = float((1 + clean).prod() ** (252 / len(clean)) - 1)
    annual_volatility = float(clean.std(ddof=1) * np.sqrt(252))
    sharpe = float((annual_return - risk_free_rate) / annual_volatility) if annual_volatility else float("nan")
    cumulative = (1 + clean).cumprod()
    drawdown = cumulative / cumulative.cummax() - 1
    var_95 = float(np.quantile(clean, 0.05))
    return {
        "annual_return": annual_return,
        "annual_volatility": annual_volatility,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
        "var_95_daily": var_95,
    }


def random_markowitz_optimize(
    returns: pd.DataFrame,
    samples: int = 20_000,
    seed: int = 202610,
    risk_free_rate: float = RISK_FREE_RATE,
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    ordered = returns.dropna()
    tickers = list(ordered.columns)
    mean_returns = ordered.mean().to_numpy() * 252
    cov = ordered.cov().to_numpy() * 252
    best: dict[str, object] | None = None

    for _ in range(samples):
        weights = rng.dirichlet(np.ones(len(tickers)))
        annual_return = float(weights @ mean_returns)
        annual_vol = float(np.sqrt(weights @ cov @ weights))
        sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol else -np.inf
        if best is None or sharpe > best["sharpe"]:
            best = {
                "weights": {ticker: float(weight) for ticker, weight in zip(tickers, weights)},
                "annual_return": annual_return,
                "annual_volatility": annual_vol,
                "sharpe": float(sharpe),
            }

    assert best is not None
    return best


def volatility_contributions(returns: pd.DataFrame, weights: dict[str, float]) -> dict[str, float]:
    ordered = returns[list(weights)].dropna()
    cov = ordered.cov().to_numpy() * 252
    w = np.array([weights[ticker] for ticker in ordered.columns])
    portfolio_vol = np.sqrt(w @ cov @ w)
    marginal = cov @ w / portfolio_vol
    contributions = w * marginal / portfolio_vol
    return {ticker: float(value) for ticker, value in zip(ordered.columns, contributions)}


def build_report(
    prices: pd.DataFrame,
    fundamentals: pd.DataFrame,
    esg: pd.DataFrame,
    macro: pd.DataFrame,
    output_path: str | Path = "outputs/multifactor_report.json",
) -> dict[str, object]:
    returns = daily_returns(prices)
    doc_series = portfolio_return_series(returns, DOCUMENT_WEIGHTS)
    doc_metrics = performance_metrics(doc_series)
    optimized = random_markowitz_optimize(returns[list(DOCUMENT_WEIGHTS)])
    optimized_series = portfolio_return_series(returns, optimized["weights"])
    optimized_metrics = performance_metrics(optimized_series)
    score_table = combine_multifactor_scores(fundamentals, esg, macro)
    macro_result = macro_holding_score(macro)
    report = {
        "macro_holding_model": macro_result,
        "document_portfolio": {
            "weights": DOCUMENT_WEIGHTS,
            "metrics": doc_metrics,
            "volatility_contribution": volatility_contributions(returns, DOCUMENT_WEIGHTS),
        },
        "optimized_portfolio": {
            "weights": optimized["weights"],
            "metrics": optimized_metrics,
        },
        "multifactor_ranking": score_table[
            [
                "ticker",
                "industry",
                "fundamental_score",
                "esg_score",
                "macro_score",
                "combined_score",
                "msci_rating",
                "sustainalytics_score",
            ]
        ].round(4).to_dict(orient="records"),
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
