#!/usr/bin/env python3
"""Run the multi-factor scoring and portfolio report pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kp_multifactor.config import DataPaths  # noqa: E402
from kp_multifactor.data_sources import create_reference_tables, load_or_create_prices  # noqa: E402
from kp_multifactor.portfolio import build_report  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data", help="Directory containing CSV tables.")
    parser.add_argument("--output", default="outputs/multifactor_report.json", help="Report JSON path.")
    parser.add_argument("--prepare-if-missing", action="store_true", help="Generate demo/reference data if missing.")
    parser.add_argument(
        "--prediction-runs",
        default=None,
        help="Optional prediction_runs.csv to merge as prediction_audit_summary.",
    )
    return parser.parse_args()


def read_table(path: Path, date_columns: list[str]) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=date_columns)


def main() -> None:
    args = parse_args()
    paths = DataPaths(
        prices=str(ROOT / args.data_dir / "prices.csv"),
        fundamentals=str(ROOT / args.data_dir / "fundamentals.csv"),
        esg=str(ROOT / args.data_dir / "esg.csv"),
        macro=str(ROOT / args.data_dir / "macro.csv"),
        portfolio=str(ROOT / args.data_dir / "portfolio.csv"),
        report=str(ROOT / args.output),
    )
    required = [paths.prices, paths.fundamentals, paths.esg, paths.macro]
    if args.prepare_if_missing and not all(Path(path).exists() for path in required):
        load_or_create_prices(paths.prices, prefer_live=False)
        create_reference_tables(ROOT / args.data_dir)

    missing = [path for path in required if not Path(path).exists()]
    if missing:
        raise SystemExit("Missing data files. Run scripts/prepare_data.py first: " + ", ".join(missing))

    report = build_report(
        prices=read_table(Path(paths.prices), ["timestamp"]),
        fundamentals=read_table(Path(paths.fundamentals), ["date"]),
        esg=read_table(Path(paths.esg), ["date"]),
        macro=read_table(Path(paths.macro), ["date"]),
        output_path=paths.report,
    )
    if args.prediction_runs:
        report["prediction_audit_summary"] = summarize_prediction_runs(ROOT / args.prediction_runs)
        Path(paths.report).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    macro = report["macro_holding_model"]
    document = report["document_portfolio"]["metrics"]
    optimized = report["optimized_portfolio"]["metrics"]
    print(f"report={paths.report}")
    print(f"macro_score={macro['score']:.2f} suggested_equity_exposure={macro['suggested_equity_exposure']:.2%}")
    print(
        "document_portfolio="
        f"annual_return={document['annual_return']:.2%} "
        f"volatility={document['annual_volatility']:.2%} "
        f"sharpe={document['sharpe']:.2f} "
        f"max_drawdown={document['max_drawdown']:.2%}"
    )
    print(
        "optimized_portfolio="
        f"annual_return={optimized['annual_return']:.2%} "
        f"volatility={optimized['annual_volatility']:.2%} "
        f"sharpe={optimized['sharpe']:.2f} "
        f"max_drawdown={optimized['max_drawdown']:.2%}"
    )
    print("ranking=" + ", ".join(item["ticker"] for item in report["multifactor_ranking"]))
    if "prediction_audit_summary" in report:
        audit = report["prediction_audit_summary"]
        print(
            "prediction_audit="
            f"runs={audit['run_count']} evaluated={audit['evaluated_count']} "
            f"avg_direction_accuracy={audit['avg_direction_accuracy']:.2%}"
        )


def summarize_prediction_runs(path: Path) -> dict:
    runs = pd.read_csv(path)
    evaluated = runs[runs["status"] == "evaluated"] if "status" in runs else pd.DataFrame()
    return {
        "run_count": int(len(runs)),
        "evaluated_count": int(len(evaluated)),
        "pending_count": int((runs["status"] == "pending_actuals").sum()) if "status" in runs else 0,
        "avg_close_mape": float(evaluated["close_mape"].mean()) if len(evaluated) else float("nan"),
        "avg_direction_accuracy": float(evaluated["direction_accuracy"].mean()) if len(evaluated) else float("nan"),
        "avg_return_error": float(evaluated["return_error"].mean()) if len(evaluated) else float("nan"),
        "by_ticker": evaluated.groupby("ticker")[["close_mape", "direction_accuracy", "return_error"]]
        .mean()
        .reset_index()
        .to_dict(orient="records")
        if len(evaluated)
        else [],
    }


if __name__ == "__main__":
    main()
