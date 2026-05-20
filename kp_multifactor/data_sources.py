"""Data loading and demo-data generation.

The module prefers externally supplied CSVs, but can generate a deterministic
contest demo dataset so the whole pipeline stays runnable without paid APIs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
import random
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

from .config import END_DATE, START_DATE, TICKERS


@dataclass(frozen=True)
class PriceProfile:
    start_price: float
    annual_return: float
    annual_vol: float
    volume_base: int


PRICE_PROFILES = {
    "ADBE": PriceProfile(226.24, -0.01, 0.33, 2_900_000),
    "LLY": PriceProfile(115.06, 0.12, 0.28, 3_400_000),
    "GOOGL": PriceProfile(52.25, 0.06, 0.31, 30_000_000),
}


def ensure_data_dir(path: str | Path = "data") -> Path:
    data_dir = Path(path)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def fetch_yahoo_prices(ticker: str, start: str = START_DATE, end: str = END_DATE) -> pd.DataFrame:
    """Fetch daily OHLCV from Yahoo's public chart endpoint.

    This intentionally has no hard dependency on yfinance. The caller should
    catch failures and use the deterministic fallback when rate-limited.
    """

    start_ts = int(pd.Timestamp(start, tz="UTC").timestamp())
    end_ts = int((pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)).timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={start_ts}&period2={end_ts}&interval=1d"
        "&events=history&includeAdjustedClose=true"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    result = payload["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    timestamps = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert(None).normalize()
    df = pd.DataFrame(
        {
            "ticker": ticker,
            "timestamp": timestamps,
            "open": quote["open"],
            "high": quote["high"],
            "low": quote["low"],
            "close": quote["close"],
            "volume": quote["volume"],
        }
    )
    df["amount"] = df["volume"] * df["close"]
    return df.dropna().reset_index(drop=True)


def generate_demo_prices(tickers: tuple[str, ...] = TICKERS) -> pd.DataFrame:
    """Generate realistic-enough daily OHLCV for the three contest tickers."""

    dates = pd.bdate_range(START_DATE, END_DATE)
    frames: list[pd.DataFrame] = []
    market_rng = np.random.default_rng(202610)
    market_noise = market_rng.normal(0.00025, 0.008, len(dates))

    for idx, ticker in enumerate(tickers):
        profile = PRICE_PROFILES[ticker]
        rng = np.random.default_rng(202600 + idx)
        daily_mu = profile.annual_return / 252
        daily_sigma = profile.annual_vol / math.sqrt(252)
        idiosyncratic = rng.normal(daily_mu, daily_sigma, len(dates))
        cycle = 0.00035 * np.sin(np.arange(len(dates)) / (42 + idx * 11))
        returns = idiosyncratic + 0.45 * market_noise + cycle
        closes = profile.start_price * np.exp(np.cumsum(returns))
        opens = np.r_[profile.start_price, closes[:-1]] * (1 + rng.normal(0, 0.003, len(dates)))
        spreads = np.abs(rng.normal(0.012, 0.004, len(dates)))
        highs = np.maximum(opens, closes) * (1 + spreads)
        lows = np.minimum(opens, closes) * (1 - spreads * rng.uniform(0.75, 1.15, len(dates)))
        volume = np.maximum(
            100_000,
            profile.volume_base * (1 + rng.normal(0, 0.18, len(dates)) + 0.08 * np.sin(np.arange(len(dates)) / 30)),
        ).astype(int)
        frame = pd.DataFrame(
            {
                "ticker": ticker,
                "timestamp": dates,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volume,
            }
        )
        frame["amount"] = frame["volume"] * frame["close"]
        frames.append(frame)

    return pd.concat(frames, ignore_index=True).round(
        {"open": 4, "high": 4, "low": 4, "close": 4, "amount": 2}
    )


def load_or_create_prices(output_path: str | Path = "data/prices.csv", prefer_live: bool = True) -> tuple[pd.DataFrame, str]:
    output = Path(output_path)
    if output.exists():
        return pd.read_csv(output, parse_dates=["timestamp"]), "existing_csv"

    frames: list[pd.DataFrame] = []
    source = "yahoo"
    if prefer_live:
        try:
            for ticker in TICKERS:
                frames.append(fetch_yahoo_prices(ticker))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, ValueError) as exc:
            frames = []
            source = f"demo_fallback_after_{type(exc).__name__}"

    if not frames:
        source = "demo_synthetic" if source == "yahoo" else source
        df = generate_demo_prices()
    else:
        df = pd.concat(frames, ignore_index=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    return df, source


def create_reference_tables(data_dir: str | Path = "data") -> dict[str, Path]:
    """Create the non-price data tables from the investment-document plan."""

    data_path = ensure_data_dir(data_dir)

    fundamentals = pd.DataFrame(
        [
            {
                "ticker": "ADBE",
                "date": "2025-10-31",
                "roe": 0.407,
                "revenue_growth": 0.103,
                "net_income_growth": 0.124,
                "pe": 27.8,
                "pb": 11.4,
                "ps": 8.6,
                "peg": 0.69,
                "fcff": 7_420_000_000,
                "z_score": 7.9,
                "industry": "Information Technology",
            },
            {
                "ticker": "LLY",
                "date": "2025-10-31",
                "roe": 0.737,
                "revenue_growth": 0.285,
                "net_income_growth": 0.356,
                "pe": 45.5,
                "pb": 48.0,
                "ps": 17.2,
                "peg": 0.48,
                "fcff": 11_800_000_000,
                "z_score": 6.2,
                "industry": "Healthcare",
            },
            {
                "ticker": "GOOGL",
                "date": "2025-10-31",
                "roe": 0.291,
                "revenue_growth": 0.137,
                "net_income_growth": 0.218,
                "pe": 24.3,
                "pb": 6.8,
                "ps": 6.4,
                "peg": 1.19,
                "fcff": 72_000_000_000,
                "z_score": 8.4,
                "industry": "Communication Services",
            },
        ]
    )

    esg = pd.DataFrame(
        [
            {
                "ticker": "ADBE",
                "date": "2025-10-31",
                "msci_rating": "AAA",
                "sustainalytics_score": 12.9,
                "governance_risk_note": "Privacy-by-design, cybersecurity, and pay-equity strengths.",
            },
            {
                "ticker": "LLY",
                "date": "2025-10-31",
                "msci_rating": "A",
                "sustainalytics_score": 16.8,
                "governance_risk_note": "Drug-pricing and commercial-practice transparency concerns.",
            },
            {
                "ticker": "GOOGL",
                "date": "2025-10-31",
                "msci_rating": "BBB",
                "sustainalytics_score": 18.5,
                "governance_risk_note": "Data privacy and market-dominance governance risks.",
            },
        ]
    )

    macro = pd.DataFrame(
        [
            {
                "date": "2025-10-31",
                "fed_rate": 0.045,
                "gdp_growth": 0.028,
                "unemployment": 0.043,
                "vix": 19.03,
                "sp500_pe_quantile": 0.95,
                "etf_flow": 1.0,
                "policy_score": 75.0,
                "fundamental_score": 80.0,
                "capital_score": 70.0,
                "black_swan_score": 85.0,
            }
        ]
    )

    portfolio = pd.DataFrame(
        [
            {"date": "2025-10-31", "ticker": "LLY", "target_weight": 0.4608, "actual_weight": 0.4608},
            {"date": "2025-10-31", "ticker": "ADBE", "target_weight": 0.2050, "actual_weight": 0.2050},
            {"date": "2025-10-31", "ticker": "GOOGL", "target_weight": 0.3342, "actual_weight": 0.3342},
        ]
    )

    outputs = {
        "fundamentals": data_path / "fundamentals.csv",
        "esg": data_path / "esg.csv",
        "macro": data_path / "macro.csv",
        "portfolio": data_path / "portfolio.csv",
    }
    fundamentals.to_csv(outputs["fundamentals"], index=False)
    esg.to_csv(outputs["esg"], index=False)
    macro.to_csv(outputs["macro"], index=False)
    portfolio.to_csv(outputs["portfolio"], index=False)
    return outputs


def write_kronos_price_files(prices: pd.DataFrame, data_dir: str | Path = "data/kronos_daily") -> list[Path]:
    """Write one Kronos-compatible OHLCV CSV per ticker."""

    output_dir = Path(data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for ticker, frame in prices.groupby("ticker"):
        kronos = frame[["timestamp", "open", "high", "low", "close", "volume", "amount"]].copy()
        kronos["timestamp"] = pd.to_datetime(kronos["timestamp"]).dt.strftime("%Y-%m-%d")
        kronos = kronos.rename(columns={"timestamp": "timestamps"})
        path = output_dir / f"{ticker}_daily.csv"
        kronos.to_csv(path, index=False)
        paths.append(path)
    return paths


def set_seed(seed: int = 202610) -> None:
    random.seed(seed)
    np.random.seed(seed)
