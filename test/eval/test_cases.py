import json
from pathlib import Path

import pytest

from chat.infrastructure.eval.runner import CaseResult, EvalReport

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


class TestEvalCases:
    @pytest.mark.eval
    @pytest.mark.parametrize("case_id", _CASE_IDS)
    def test_case_passes(self, case_id: str, eval_report: EvalReport) -> None:
        # Arrange
        result = next(c for c in eval_report.cases if c.case_id == case_id)
        # Assert
        assert result.passed, _format_failure(result)
