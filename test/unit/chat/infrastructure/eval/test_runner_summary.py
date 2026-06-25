from chat.infrastructure.eval.metrics import NodeMetrics
from chat.infrastructure.eval.runner import CaseResult, compute_summary


def _case(
    case_id: str,
    passed: bool,
    latency_s: float,
    output_tokens: int,
    tags: list[str],
) -> CaseResult:
    nodes = {
        "generate_sql": NodeMetrics(
            latency_s=latency_s, input_tokens=10, output_tokens=output_tokens
        )
    }
    return CaseResult(
        case_id=case_id,
        question="q",
        nodes=nodes,
        sql_query="SELECT 1",
        sql_valid=True,
        response="r",
        check_results=[],
        passed=passed,
        error=None,
        tags=tags,
    )


class TestComputeSummaryCounts:
    def test_reports_pass_rate(self) -> None:
        # arrange
        cases = [
            _case("a", True, 1.0, 100, ["easy"]),
            _case("b", False, 1.0, 100, ["hard"]),
        ]
        # act
        summary = compute_summary(cases)
        # assert
        assert summary["passed"] == 1
        assert summary["pass_rate"] == 0.5


class TestComputeSummaryLatency:
    def test_p95_latency_uses_slowest_for_small_samples(self) -> None:
        # arrange — p95 of a few cases lands on the slowest
        cases = [_case(str(i), True, float(i), 100, ["easy"]) for i in range(1, 11)]
        # act
        summary = compute_summary(cases)
        # assert
        assert summary["p95_latency_s"] == 10.0


class TestComputeSummaryCost:
    def test_cost_from_token_prices(self) -> None:
        # arrange — 1M output tokens at $2/M = $2.00
        cases = [_case("a", True, 1.0, 1_000_000, ["easy"])]
        # act
        summary = compute_summary(cases, input_price_per_m=1.0, output_price_per_m=2.0)
        # assert — 10 input tokens (~$0.00001) + 1M output ($2.00)
        assert round(float(summary["cost_usd"]), 2) == 2.00


class TestComputeSummaryByTag:
    def test_breaks_down_pass_rate_by_tag(self) -> None:
        # arrange
        cases = [
            _case("a", True, 1.0, 100, ["aggregation", "easy"]),
            _case("b", False, 1.0, 100, ["aggregation", "hard"]),
        ]
        # act
        by_tag = compute_summary(cases)["by_tag"]
        # assert
        assert by_tag["aggregation"] == {"total": 2, "passed": 1}
        assert by_tag["hard"] == {"total": 1, "passed": 0}
