from chat.infrastructure.eval.metrics import NodeMetrics
from chat.infrastructure.eval.runner import (
    CaseResult,
    _count_passed,
    _percentile,
    _sum_node_token_attr,
    compute_summary,
)


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


class TestCountPassed:
    def test_counts_one_per_passing_case(self) -> None:
        # arrange — 2 passing cases to distinguish from "sum(2 for ...)" mutation
        cases = [
            _case("a", True, 0, 0, []),
            _case("b", True, 0, 0, []),
            _case("c", False, 0, 0, []),
        ]
        # act / assert
        assert _count_passed(cases) == 2

    def test_returns_zero_for_all_failed(self) -> None:
        cases = [_case("a", False, 0, 0, []), _case("b", False, 0, 0, [])]
        assert _count_passed(cases) == 0


class TestPercentile:
    def test_returns_zero_for_empty_list(self) -> None:
        assert _percentile([], 0.95) == 0.0

    def test_returns_max_for_p100(self) -> None:
        assert _percentile([1.0, 2.0, 3.0], 1.0) == 3.0


class TestSumNodeTokenAttr:
    def test_returns_zero_when_all_tokens_are_zero(self) -> None:
        # arrange — nodes with 0 tokens; distinguishes "or 0" from "or 1"
        cases = [_case("a", True, 0, 0, [])]
        # act / assert
        assert _sum_node_token_attr(cases, "output_tokens") == 0

    def test_sums_across_all_nodes_and_cases(self) -> None:
        nodes_a = {"n1": NodeMetrics(latency_s=0, input_tokens=10, output_tokens=5)}
        nodes_b = {"n1": NodeMetrics(latency_s=0, input_tokens=20, output_tokens=8)}
        cases = [
            CaseResult("a", "q", nodes_a, "", True, "", [], True, None),
            CaseResult("b", "q", nodes_b, "", True, "", [], True, None),
        ]
        assert _sum_node_token_attr(cases, "input_tokens") == 30
        assert _sum_node_token_attr(cases, "output_tokens") == 13


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

    def test_reports_total_and_failed(self) -> None:
        # arrange — 3 cases, 1 passed
        cases = [
            _case("a", True, 0, 0, []),
            _case("b", False, 0, 0, []),
            _case("c", False, 0, 0, []),
        ]
        # act
        summary = compute_summary(cases)
        # assert
        assert summary["total"] == 3
        assert summary["failed"] == 2

    def test_zero_cases_returns_zero_pass_rate(self) -> None:
        # arrange
        summary = compute_summary([])
        # assert — empty case list must not raise and must give sensible zeros
        assert summary["total"] == 0
        assert summary["pass_rate"] == 0.0
        assert summary["avg_latency_s"] == 0.0

    def test_reports_token_counts(self) -> None:
        # arrange — 10 input, 100 output tokens
        cases = [_case("a", True, 0, 100, [])]
        # act
        summary = compute_summary(cases)
        # assert
        assert summary["total_output_tokens"] == 100
        assert summary["total_input_tokens"] == 10  # NodeMetrics uses input_tokens=10 in _case()

    def test_reports_avg_output_tokens(self) -> None:
        # arrange — 2 cases with 100 output tokens each
        cases = [_case("a", True, 0, 100, []), _case("b", False, 0, 100, [])]
        # act
        summary = compute_summary(cases)
        # assert
        assert summary["avg_output_tokens"] == 100.0

    def test_default_prices_produce_zero_cost(self) -> None:
        # arrange — calling without prices should yield cost_usd == 0
        cases = [_case("a", True, 0, 1_000, [])]
        # act
        summary = compute_summary(cases)
        # assert — distinguishes default=0.0 from default=1.0 mutations
        assert summary["cost_usd"] == 0.0


class TestComputeSummaryLatency:
    def test_p95_latency_uses_slowest_for_small_samples(self) -> None:
        # arrange — p95 of a few cases lands on the slowest
        cases = [_case(str(i), True, float(i), 100, ["easy"]) for i in range(1, 11)]
        # act
        summary = compute_summary(cases)
        # assert
        assert summary["p95_latency_s"] == 10.0

    def test_avg_latency_rounds_to_three_decimal_places(self) -> None:
        # arrange — avg of 1/3 differs at 3 vs 4 decimal places
        cases = [
            _case("a", True, 1.0, 0, []),
            _case("b", True, 0.0, 0, []),
            _case("c", True, 0.0, 0, []),
        ]
        # act
        summary = compute_summary(cases)
        # assert — 1/3 = 0.333... rounds to 0.333 at 3 places, 0.3333 at 4 places
        assert summary["avg_latency_s"] == round(1 / 3, 3)

    def test_avg_latency_is_float_not_int(self) -> None:
        # arrange — avg latency 1.5; round(1.5, None) = 2 (int) but round(1.5, 3) = 1.5
        cases = [_case("a", True, 1.0, 0, []), _case("b", True, 2.0, 0, [])]
        # act
        summary = compute_summary(cases)
        # assert — must be float 1.5, not int 2 (mutmut_47 rounds with None)
        assert summary["avg_latency_s"] == 1.5

    def test_p95_latency_rounds_to_three_decimal_places(self) -> None:
        # arrange — p95 of a list where the value has more than 3 significant decimals
        # p95 of [1.0, 1.0, ..., 1.5] with 20 items = 1.475 → 1.475 at 3 places vs 2 with None
        cases = [_case(str(i), True, 1.0 if i < 19 else 1.5, 0, []) for i in range(20)]
        # act
        summary = compute_summary(cases)
        # assert — p95 must be a precise float, not truncated to int
        assert isinstance(summary["p95_latency_s"], float)
        assert summary["p95_latency_s"] < 2.0  # mutmut_57 rounds to None → may give 2


class TestComputeSummaryCost:
    def test_cost_from_token_prices(self) -> None:
        # arrange — 1M output tokens at $2/M, input_price=0 to isolate output cost
        cases = [_case("a", True, 1.0, 1_000_000, ["easy"])]
        # act
        summary = compute_summary(cases, input_price_per_m=0.0, output_price_per_m=2.0)
        # assert — exact: 1M * 2.0 / 1_000_000 = 2.0; mutmut_27 divides by 1_000_001 → 1.999998
        assert float(summary["cost_usd"]) == 2.0

    def test_pass_rate_rounds_to_three_decimal_places(self) -> None:
        # arrange — 1 passed out of 3; 1/3 = 0.333 at 3 places, 0.3333 at 4 places
        cases = [
            _case("a", True, 0, 0, []),
            _case("b", False, 0, 0, []),
            _case("c", False, 0, 0, []),
        ]
        # act
        summary = compute_summary(cases)
        # assert — must be exactly 3 decimal places
        assert summary["pass_rate"] == round(1 / 3, 3)


class TestComputeSummaryPrecision:
    def test_p95_latency_rounds_to_3_not_4_decimal_places(self) -> None:
        # kills mutmut_65 (round(..., 4) vs round(..., 3))
        # p95 of a single value 1/3 = 0.3333...; at 3 decimals: 0.333, at 4: 0.3333
        cases = [_case("a", True, 1 / 3, 0, [])]
        summary = compute_summary(cases)
        assert summary["p95_latency_s"] == round(1 / 3, 3)
        assert summary["p95_latency_s"] != round(1 / 3, 4)

    def test_avg_output_tokens_is_float_with_1_decimal(self) -> None:
        # kills mutmut_73/75 (round(x, None) or round(x,) → int)
        # 5 tokens / 3 cases = 1.666... → 1.7 at 1dp, 1.67 at 2dp
        cases = [
            _case("a", True, 0, 5, []),
            _case("b", False, 0, 0, []),
            _case("c", False, 0, 0, []),
        ]
        summary = compute_summary(cases)
        # kills mutmut_77 (round(..., 2) gives 1.67 not 1.7)
        assert summary["avg_output_tokens"] == round(5 / 3, 1)
        assert isinstance(summary["avg_output_tokens"], float)

    def test_avg_output_tokens_is_zero_when_no_cases(self) -> None:
        # kills mutmut_78 (else 1.0 instead of else 0.0)
        summary = compute_summary([])
        assert summary["avg_output_tokens"] == 0.0

    def test_cost_usd_rounds_to_6_not_7_decimal_places(self) -> None:
        # kills mutmut_82/84 (round(cost, None) or round(cost,) → int)
        # kills mutmut_85 (round(cost, 7) vs round(cost, 6))
        # cost = 1_234_567 * 0.1 / 1e6 = 0.1234567
        # round(0.1234567, 6) = 0.123457 (7th digit=7 rounds UP the 6th)
        # round(0.1234567, 7) = 0.1234567 (different!)
        # round(0.1234567)    = 0 (int — for None/missing ndigits)
        cases = [_case("a", True, 0, 1_234_567, [])]
        summary = compute_summary(cases, input_price_per_m=0.0, output_price_per_m=0.1)
        assert isinstance(summary["cost_usd"], float)
        assert summary["cost_usd"] == round(1_234_567 * 0.1 / 1e6, 6)


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
