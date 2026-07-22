"""Tests for the eval trend table's reading of reports and summaries."""

import json
from pathlib import Path

from scripts.eval_trend import _load_rows


def _write(directory: Path, name: str, run_at: str, pass_rate: float) -> None:
    document = {
        "run_at": run_at,
        "model": "openai/glm-4",
        "summary": {"pass_rate": pass_rate},
    }
    (directory / name).write_text(json.dumps(document))


class TestLoadRows:
    def test_reads_the_full_reports_already_in_the_repository(self, tmp_path: Path) -> None:
        # arrange — the runs recorded before summaries existed
        _write(tmp_path, "eval_report_1.json", "2026-01-01T00:00:00", 0.5)
        # act
        rows = _load_rows(tmp_path)
        # assert
        assert [row["pass_rate"] for row in rows] == [0.5]

    def test_reads_the_summaries_written_from_now_on(self, tmp_path: Path) -> None:
        # arrange
        _write(tmp_path, "eval_summary_2.json", "2026-02-01T00:00:00", 0.9)
        # act
        rows = _load_rows(tmp_path)
        # assert
        assert [row["pass_rate"] for row in rows] == [0.9]

    def test_counts_a_run_once_when_both_of_its_files_are_present(self, tmp_path: Path) -> None:
        # A run writes both, and the full report is only absent once git ignores it — on the
        # machine that produced it, both sit in the directory and describe the same run.
        _write(tmp_path, "eval_report_3.json", "2026-03-01T00:00:00", 0.7)
        _write(tmp_path, "eval_summary_3.json", "2026-03-01T00:00:00", 0.7)
        # act
        rows = _load_rows(tmp_path)
        # assert
        assert len(rows) == 1

    def test_orders_runs_oldest_first_across_both_kinds(self, tmp_path: Path) -> None:
        # arrange
        _write(tmp_path, "eval_summary_2.json", "2026-02-01T00:00:00", 0.9)
        _write(tmp_path, "eval_report_1.json", "2026-01-01T00:00:00", 0.5)
        # act
        rows = _load_rows(tmp_path)
        # assert — the trend only reads as a trend in order
        assert [row["run_at"] for row in rows] == [
            "2026-01-01T00:00:00",
            "2026-02-01T00:00:00",
        ]

    def test_no_reports_means_no_rows(self, tmp_path: Path) -> None:
        assert _load_rows(tmp_path) == []
