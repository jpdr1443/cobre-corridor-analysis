"""Full pipeline for the Cobre L2 Business Architect assessment.

Usage:
    python main.py              # runs everything and writes to ../outputs
    python main.py --quiet      # do not print tables to the console
"""
from __future__ import annotations

import argparse

import pandas as pd

from cobre import config as cfg
from cobre import part1, part2, part3, quality, report
from cobre.data import get_data, load_raw
from cobre.export import export


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="do not print tables")
    args = parser.parse_args()

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 160)
    pd.options.display.float_format = "{:,.4f}".format

    tx_raw, _ = load_raw()
    df, users = get_data()

    results = [quality.run(tx_raw, users, df),
               *part1.run(df, users),
               part2.run(df),
               part3.run(df)]

    if not args.quiet:
        for r in results:
            for name, t in r.tables.items():
                print(f"\n=== {name} ===\n{t}")

    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = export(results, df, users, cfg.OUTPUT_DIR)
    md = report.write(results, cfg.OUTPUT_DIR / "findings_report.md")

    print("\nDone:")
    for k, p in {**paths, "report": md}.items():
        print(f"  {k:8s} -> {p}")


if __name__ == "__main__":
    main()
