"""Tests for what an eval run writes to disk."""

import json
from pathlib import Path

from chat.infrastructure.eval.runner import EvalReport
from scripts.run_eval import _report_path, _summary_path, _trend_summary


def _report() -> EvalReport:
    return EvalReport(
        run_at="2026-07-22T12:00:00",
        model="openai/glm-4",
        summary={"total": 366, "pass_rate": 0.959},
        cases=[],
    )


class TestSummaryPath:
    def test_sits_beside_the_full_report_under_the_same_run(self) -> None:
        # arrange
        report = _report()
        # act
        summary = _summary_path(Path("reports"), report)
        # assert — same epoch as the report, so the pair is obvious in a directory listing
        epoch = _report_path(Path("reports"), report).stem.removeprefix("eval_report_")
        assert summary == Path("reports") / f"eval_summary_{epoch}.json"


class TestTrendSummary:
    def test_carries_what_the_trend_table_reads(self) -> None:
        # arrange / act
        summary = _trend_summary(_report())
        # assert
        assert summary == {
            "run_at": "2026-07-22T12:00:00",
            "model": "openai/glm-4",
            "summary": {"total": 366, "pass_rate": 0.959},
        }

    def test_leaves_out_the_per_case_detail(self) -> None:
        # The per-case rows are what pushed a report past the commit hook's size limit;
        # keeping them out is the whole point of the summary existing.
        assert "cases" not in _trend_summary(_report())

    def test_stays_small_enough_to_keep_forever(self) -> None:
        # arrange — a report the size of a real run
        report = EvalReport(
            run_at="2026-07-22T12:00:00",
            model="m",
            summary={"total": 366},
            cases=[{"case_id": f"c-{i}", "nodes": {"a": 1}} for i in range(366)],  # type: ignore[list-item]
        )
        # act
        written = json.dumps(_trend_summary(report))
        # assert — kilobytes, not megabytes
        assert len(written) < 1024
