#!/usr/bin/env python3
"""Audit Kronos WebUI prediction results and generate research logs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kp_multifactor.prediction_audit import audit_result_files  # noqa: E402
from kp_multifactor.research_writer import write_research_notes  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        default="kronos_repo/webui/prediction_results",
        help="Directory containing Kronos WebUI prediction JSON files.",
    )
    parser.add_argument("--output-dir", default="outputs/research_log", help="Directory for audit CSV/Markdown files.")
    parser.add_argument("--ticker", help="Only keep runs inferred as this ticker, e.g. ADBE.")
    parser.add_argument(
        "--multifactor-report",
        default="outputs/multifactor_report.json",
        help="Optional multi-factor report JSON to enrich research notes.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results_dir = ROOT / args.results_dir
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = sorted(results_dir.glob("*.json"))
    if not paths:
        raise SystemExit(f"No Kronos JSON files found in {results_dir}")

    runs, points = audit_result_files(paths)
    if args.ticker:
        ticker = args.ticker.upper()
        runs = runs[runs["ticker"] == ticker]
        points = points[points["ticker"] == ticker] if not points.empty else points

    runs_path = output_dir / "prediction_runs.csv"
    points_path = output_dir / "prediction_points.csv"
    notes_path = output_dir / "research_notes.md"

    runs.to_csv(runs_path, index=False)
    points.to_csv(points_path, index=False)
    multifactor_report = _load_json(ROOT / args.multifactor_report)
    write_research_notes(runs, multifactor_report, notes_path)

    evaluated = int((runs["status"] == "evaluated").sum()) if "status" in runs else 0
    pending = int((runs["status"] == "pending_actuals").sum()) if "status" in runs else 0
    print(f"runs={runs_path} rows={len(runs)} evaluated={evaluated} pending={pending}")
    print(f"points={points_path} rows={len(points)}")
    print(f"notes={notes_path}")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
