"""Summarise eval reports over time into a trend table.

Reads every reports/eval_report_*.json and prints one chronological row per run
(pass rate, latency, output tokens, cost) so quality and cost trends are visible
to non-technical stakeholders without opening the raw JSON.

Usage:
    python scripts/eval_trend.py
    python scripts/eval_trend.py --reports-dir reports
"""

import argparse
import json
from pathlib import Path
from typing import cast

_COLUMNS = (
    "run_at",
    "model",
    "pass_rate",
    "avg_latency_s",
    "p95_latency_s",
    "total_output_tokens",
    "cost_usd",
)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eval_trend",
        description="Print a chronological trend table from eval JSON reports.",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        metavar="PATH",
        help="Directory holding eval_report_*.json files (default: reports)",
    )
    return parser


def _load_rows(reports_dir: Path) -> list[dict[str, object]]:
    """Return one summary row per report, sorted by run timestamp."""
    rows: list[dict[str, object]] = []
    for path in reports_dir.glob("eval_report_*.json"):
        report = cast(dict[str, object], json.loads(path.read_text()))
        summary = cast(dict[str, object], report.get("summary", {}))
        rows.append(
            {
                "run_at": report.get("run_at", "?"),
                "model": report.get("model", "?"),
                **{key: summary.get(key, "-") for key in _COLUMNS[2:]},
            }
        )
    return sorted(rows, key=lambda r: str(r["run_at"]))


def _print_table(rows: list[dict[str, object]]) -> None:
    if not rows:
        print("No eval reports found.")
        return
    print(" | ".join(f"{col:>20}" for col in _COLUMNS))
    for row in rows:
        print(" | ".join(f"{str(row.get(col, '-')):>20}" for col in _COLUMNS))


def main() -> None:
    """Parse args and print the trend table to stdout."""
    args = _build_arg_parser().parse_args()
    _print_table(_load_rows(Path(args.reports_dir)))


if __name__ == "__main__":
    main()
