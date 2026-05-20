#!/usr/bin/env python3
"""Prepare contest data tables for the K-predict prototype."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kp_multifactor.data_sources import (  # noqa: E402
    create_reference_tables,
    load_or_create_prices,
    write_kronos_price_files,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data", help="Directory for generated CSV tables.")
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="Skip live price downloads and generate deterministic demo prices.",
    )
    parser.add_argument(
        "--overwrite-prices",
        action="store_true",
        help="Delete existing prices.csv before preparing data.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = ROOT / args.data_dir
    prices_path = data_dir / "prices.csv"
    if args.overwrite_prices and prices_path.exists():
        prices_path.unlink()

    prices, source = load_or_create_prices(prices_path, prefer_live=not args.no_live)
    reference_paths = create_reference_tables(data_dir)
    kronos_paths = write_kronos_price_files(prices, data_dir / "kronos_daily")

    print(f"price_source={source}")
    print(f"prices={prices_path} rows={len(prices)}")
    for name, path in reference_paths.items():
        print(f"{name}={path}")
    for path in kronos_paths:
        print(f"kronos_csv={path}")


if __name__ == "__main__":
    main()
