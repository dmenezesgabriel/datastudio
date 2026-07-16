import json
from pathlib import Path
from typing import cast

import pytest

from chat.infrastructure.eval.runner import CaseResult, EvalReport
from shared.infrastructure.config.settings import AppSettings

_CASES_PATH = Path(__file__).parent / "cases.json"
_CASE_IDS = [c["id"] for c in json.loads(_CASES_PATH.read_text())["cases"]]


def _format_failure(result: CaseResult) -> str:
    lines = [f"Case '{result.case_id}' failed"]
    if result.error:
        lines.append(f"  error: {result.error}")
    for cr in result.check_results:
        if not cr["passed"]:
            label = f"{cr['type']}={cr['value']!r}" if cr["value"] else cr["type"]
            reason = f" — {cr['reasoning']}" if cr.get("reasoning") else ""
            lines.append(f"  ✗ {label}{reason}")
    return "\n".join(lines)


def _consistency_failure(case_id: str, report: EvalReport, floor: float) -> str:
    """Report the case's pass@k rate plus one failed attempt's checks for diagnosis."""
    record = next(c for c in report.consistency if c.case_id == case_id)
    header = (
        f"Case '{case_id}' consistency {record.consistency} "
        f"({record.passed_count}/{record.attempts}) < floor {floor}"
    )
    failed = next((c for c in report.cases if c.case_id == case_id and not c.passed), None)
    return header if failed is None else f"{header}\n{_format_failure(failed)}"


class TestEvalCases:
    @pytest.mark.eval
    @pytest.mark.parametrize("case_id", _CASE_IDS)
    def test_case_meets_consistency(
        self, case_id: str, eval_report: EvalReport, app_settings: AppSettings
    ) -> None:
        # Arrange — a case runs eval_repeats times; grade its pass@k, not a single attempt.
        floor = app_settings.eval_min_consistency
        record = next(c for c in eval_report.consistency if c.case_id == case_id)
        # Assert
        assert record.consistency >= floor, _consistency_failure(case_id, eval_report, floor)


class TestEvalBudgets:
    """Production SLO gates — a run that regresses past these thresholds fails CI."""

    @pytest.mark.eval
    def test_pass_rate_meets_target(
        self, eval_report: EvalReport, app_settings: AppSettings
    ) -> None:
        # Assert
        pass_rate = float(eval_report.summary["pass_rate"])  # type: ignore[arg-type]
        assert pass_rate >= app_settings.eval_min_pass_rate, (
            f"pass_rate {pass_rate} < target {app_settings.eval_min_pass_rate}"
        )

    @pytest.mark.eval
    def test_mean_consistency_meets_target(
        self, eval_report: EvalReport, app_settings: AppSettings
    ) -> None:
        # Assert — the suite as a whole must clear the consistency floor, not just each case.
        consistency = cast(dict[str, object], eval_report.summary["consistency"])
        mean = float(cast(float, consistency["mean_consistency"]))
        assert mean >= app_settings.eval_min_consistency, (
            f"mean consistency {mean} < target {app_settings.eval_min_consistency}"
        )

    @pytest.mark.eval
    def test_p95_latency_within_budget(
        self, eval_report: EvalReport, app_settings: AppSettings
    ) -> None:
        # Assert
        p95 = float(eval_report.summary["p95_latency_s"])  # type: ignore[arg-type]
        assert p95 <= app_settings.eval_max_p95_latency_s, (
            f"p95 latency {p95}s > budget {app_settings.eval_max_p95_latency_s}s"
        )

    @pytest.mark.eval
    def test_avg_output_tokens_within_budget(
        self, eval_report: EvalReport, app_settings: AppSettings
    ) -> None:
        # Assert
        avg_out = float(eval_report.summary["avg_output_tokens"])  # type: ignore[arg-type]
        assert avg_out <= app_settings.eval_max_avg_output_tokens, (
            f"avg output tokens {avg_out} > budget {app_settings.eval_max_avg_output_tokens}"
        )

    @pytest.mark.eval
    def test_avg_input_tokens_within_budget(
        self, eval_report: EvalReport, app_settings: AppSettings
    ) -> None:
        # Guards against conversation-memory bloat: injected history is billed as input.
        avg_in = float(eval_report.summary["avg_input_tokens"])  # type: ignore[arg-type]
        assert avg_in <= app_settings.eval_max_avg_input_tokens, (
            f"avg input tokens {avg_in} > budget {app_settings.eval_max_avg_input_tokens}"
        )
