"""Eval runner: orchestrates EvalCases through the instrumented graph."""

import datetime
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, cast

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.eval.checks import Check, CheckResult
from chat.infrastructure.eval.metrics import EvalCollector, MetricsRecorder, NodeMetrics
from chat.infrastructure.eval.token_callback import TokenCountingCallback
from chat.infrastructure.graph.types import TypedChatGraph


@dataclass
class EvalCase:
    """A single evaluation case: a question plus a set of correctness checks."""

    id: str
    question: str
    checks: list[Check]
    tags: list[str] = field(default_factory=list[str])


@dataclass
class CaseResult:
    """Outcome of running one EvalCase through the instrumented graph."""

    case_id: str
    question: str
    nodes: dict[str, NodeMetrics]
    sql_query: str
    sql_valid: bool
    response: str
    check_results: list[CheckResult]
    passed: bool
    error: str | None
    tags: list[str] = field(default_factory=list[str])


@dataclass
class EvalReport:
    """Full eval run report, ready for JSON serialisation via dataclasses.asdict."""

    run_at: str
    model: str
    summary: dict[str, object]
    cases: list[CaseResult]


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile; returns the slowest for small samples at p95."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil(pct * len(ordered)) - 1)
    return ordered[rank]


def _count_passed(cases: list[CaseResult]) -> int:
    """Count cases where all checks passed."""
    return sum(1 for c in cases if c.passed)


def _case_latencies(cases: list[CaseResult]) -> list[float]:
    """Sum node latencies per case, returning one value per case."""
    return [sum(m.latency_s for m in c.nodes.values()) for c in cases]


def _sum_node_token_attr(
    cases: list[CaseResult],
    attr: Literal["input_tokens", "output_tokens"],
) -> int:
    """Sum a token count attribute across all nodes in all cases."""
    return sum((getattr(m, attr) or 0) for c in cases for m in c.nodes.values())


def _by_tag(cases: list[CaseResult]) -> dict[str, dict[str, int]]:
    """Pass/total counts per tag, for stratified accuracy reporting."""
    breakdown: dict[str, dict[str, int]] = {}
    for case in cases:
        for tag in case.tags:
            bucket = breakdown.setdefault(tag, {"total": 0, "passed": 0})
            bucket["total"] += 1
            bucket["passed"] += int(case.passed)
    return breakdown


def compute_summary(
    cases: list[CaseResult],
    input_price_per_m: float = 0.0,
    output_price_per_m: float = 0.0,
) -> dict[str, object]:
    """Aggregate per-case results into headline metrics, SLOs, and per-tag accuracy.

    Token prices (USD per million tokens) drive cost_usd; default 0.0 leaves it
    at zero when pricing is not configured.
    """
    total = len(cases)
    passed = _count_passed(cases)
    latencies = _case_latencies(cases)
    input_tokens = _sum_node_token_attr(cases, "input_tokens")
    output_tokens = _sum_node_token_attr(cases, "output_tokens")
    cost = (input_tokens * input_price_per_m + output_tokens * output_price_per_m) / 1e6
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "avg_latency_s": round(sum(latencies) / total, 3) if total else 0.0,
        "p95_latency_s": round(_percentile(latencies, 0.95), 3),
        "total_input_tokens": input_tokens,
        "total_output_tokens": output_tokens,
        "avg_output_tokens": round(output_tokens / total, 1) if total else 0.0,
        "cost_usd": round(cost, 6),
        "by_tag": _by_tag(cases),
    }


class EvalRunner:
    """Runs EvalCases through the instrumented graph and returns an EvalReport.

    Accepts a graph_factory callable so that graph construction (and the
    dependencies it needs — models, engines) stays outside this class. Each
    case receives a fresh EvalCollector; the factory is called once per case
    with that collector so metrics are isolated per case.

    Example:
        runner = EvalRunner(
            graph_factory=lambda r: build_text2sql_graph(model, engine, recorder=r),
            model_name="openai/glm-5",
        )
        report = runner.run(cases)
    """

    def __init__(
        self,
        graph_factory: Callable[[MetricsRecorder], TypedChatGraph],
        model_name: str,
        input_price_per_m: float = 0.0,
        output_price_per_m: float = 0.0,
    ) -> None:
        """Store the factory and pricing; graph construction happens per case in run()."""
        self._graph_factory = graph_factory
        self._model_name = model_name
        self._input_price_per_m = input_price_per_m
        self._output_price_per_m = output_price_per_m

    def run(self, cases: list[EvalCase]) -> EvalReport:
        """Run all cases sequentially and return a consolidated report."""
        results = [self._run_case(case) for case in cases]
        return EvalReport(
            run_at=datetime.datetime.now(datetime.UTC).isoformat(),
            model=self._model_name,
            summary=compute_summary(results, self._input_price_per_m, self._output_price_per_m),
            cases=results,
        )

    def _run_case(self, case: EvalCase) -> CaseResult:
        collector = EvalCollector()
        graph = self._graph_factory(collector)
        callback = TokenCountingCallback(collector)
        try:
            raw = graph.invoke(  # pyright: ignore[reportUnknownMemberType]
                cast(ChatState, {"question": case.question}),
                config={"callbacks": [callback]},
            )
            state = cast(ChatState, raw)
            state_dict = cast(dict[str, object], state)
            check_results = [c.evaluate(state) for c in case.checks]
            return CaseResult(
                case_id=case.id,
                question=case.question,
                nodes=collector.node_metrics,
                sql_query=str(state_dict.get("sql_query", "")),
                sql_valid=bool(state_dict.get("query_result")),
                response=str(state_dict.get("response", "")),
                check_results=check_results,
                passed=all(r["passed"] for r in check_results),
                error=None,
                tags=case.tags,
            )
        except Exception as exc:
            return CaseResult(
                case_id=case.id,
                question=case.question,
                nodes=collector.node_metrics,
                sql_query="",
                sql_valid=False,
                response="",
                check_results=[],
                passed=False,
                error=str(exc),
                tags=case.tags,
            )
