"""Eval runner: orchestrates EvalCases through the instrumented graph."""

import datetime
import math
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Literal, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.eval.checks import Check, CheckResult
from chat.infrastructure.eval.metrics import EvalCollector, MetricsRecorder, NodeMetrics
from chat.infrastructure.eval.token_callback import TokenCountingCallback
from chat.infrastructure.graph.types import TypedChatGraph


@dataclass
class EvalTurn:
    """One turn within a case: a question and the checks asserted on its answer.

    Follow-up turns are how short-term memory is graded: a turn whose question only
    resolves against prior turns (e.g. "now break it down by month") passes only when
    the accumulated conversation history reaches the graph.
    """

    question: str
    checks: list[Check]


@dataclass
class EvalCase:
    """An evaluation case: a base question plus optional follow-up turns.

    ``question``/``checks`` are the first turn; ``follow_ups`` are later turns in the
    same conversation, run with the prior turns injected as history. A case with no
    ``follow_ups`` is an ordinary single-turn case.
    """

    id: str
    question: str
    checks: list[Check]
    tags: list[str] = field(default_factory=list[str])
    follow_ups: list[EvalTurn] = field(default_factory=list[EvalTurn])


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


def _case_turns(case: EvalCase) -> list[EvalTurn]:
    """The case as an ordered turn list: the base question then any follow-ups."""
    return [EvalTurn(case.question, case.checks), *case.follow_ups]


def _widget_results(state_dict: dict[str, object]) -> list[WidgetResult]:
    """Every widget's executed result off the aggregated ``widget_results`` channel.

    The orchestrator–workers graph keeps ``sql_query``/``query_result`` local to each
    ``build_widget`` worker, so they never surface on the top-level state — the SQL and
    validity a report shows must be read back from the aggregated widget results.
    """
    raw = state_dict.get("widget_results")
    items = cast(list[object], raw) if isinstance(raw, list) else []
    return [item for item in items if isinstance(item, WidgetResult)]


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
    attr: Literal["input_tokens", "output_tokens", "cached_input_tokens"],
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


# The checks that grade "did the agent choose the right response shape" (text vs KPI vs
# chart vs table vs dashboard) — as opposed to structural/data-correctness checks. Their
# aggregate accuracy is surfaced as a headline metric so response-type selection is
# visible without slicing per-tag.
_VIEW_SELECTION_CHECKS = frozenset(
    {"view_present", "view_contains", "chart_fit", "viz_rubric", "widget_count", "text_answer"}
)


def _view_selection_accuracy(cases: list[CaseResult]) -> dict[str, object]:
    """Pass/total/accuracy over the response-type-selection checks across all cases."""
    total = passed = 0
    for case in cases:
        for check in case.check_results:
            if check["type"] in _VIEW_SELECTION_CHECKS:
                total += 1
                passed += int(check["passed"])
    return {
        "passed": passed,
        "total": total,
        "accuracy": round(passed / total, 3) if total else 0.0,
    }


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
    cached_input_tokens = _sum_node_token_attr(cases, "cached_input_tokens")
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
        # cached_input is a subset of input, not subtracted — effective-fresh is input − cached.
        "total_cached_input_tokens": cached_input_tokens,
        "cache_read_rate": round(cached_input_tokens / input_tokens, 3) if input_tokens else 0.0,
        "avg_input_tokens": round(input_tokens / total, 1) if total else 0.0,
        "avg_output_tokens": round(output_tokens / total, 1) if total else 0.0,
        "cost_usd": round(cost, 6),
        "view_selection": _view_selection_accuracy(cases),
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
            graph_factory=lambda r: build_eval_graph(model, engine, r),
            model_name="openai/glm-5",
            max_workers=4,
        )
        report = runner.run(cases)
    """

    def __init__(
        self,
        graph_factory: Callable[[MetricsRecorder], TypedChatGraph],
        model_name: str,
        input_price_per_m: float = 0.0,
        output_price_per_m: float = 0.0,
        max_workers: int = 1,
    ) -> None:
        """Store the factory, pricing, and concurrency; graphs are built per case in run().

        max_workers > 1 runs cases through a bounded thread pool. Each case
        already gets its own graph + collector, and the SqlEnginePort opens a
        fresh read-only connection per call, so cases are isolated — keep the
        bound modest since the real ceiling is upstream LLM rate limits.
        """
        self._graph_factory = graph_factory
        self._model_name = model_name
        self._input_price_per_m = input_price_per_m
        self._output_price_per_m = output_price_per_m
        self._max_workers = max_workers

    def run(self, cases: list[EvalCase]) -> EvalReport:
        """Run all cases and return a consolidated report."""
        results = self._run_cases(cases)
        return EvalReport(
            run_at=datetime.datetime.now(datetime.UTC).isoformat(),
            model=self._model_name,
            summary=compute_summary(results, self._input_price_per_m, self._output_price_per_m),
            cases=results,
        )

    def _run_cases(self, cases: list[EvalCase]) -> list[CaseResult]:
        """Run cases sequentially, or via a thread pool when max_workers > 1.

        Results keep input order in both paths (ThreadPoolExecutor.map preserves
        ordering), so the report is deterministic regardless of completion order.
        """
        if self._max_workers <= 1:
            return [self._run_case(case) for case in cases]
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            return list(pool.map(self._run_case, cases))

    def _run_case(self, case: EvalCase) -> CaseResult:
        # One collector spans all turns so node latency/tokens reflect the whole
        # conversation — a follow-up's injected history shows up as extra input tokens.
        collector = EvalCollector()
        callback = TokenCountingCallback(collector)
        try:
            check_results, state_dict = self._run_turns(case, collector, callback)
            widget_results = _widget_results(state_dict)
            return CaseResult(
                case_id=case.id,
                question=case.question,
                nodes=collector.node_metrics,
                sql_query="; ".join(r.sql for r in widget_results),
                sql_valid=bool(widget_results),
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

    def _run_turns(
        self, case: EvalCase, collector: MetricsRecorder, callback: TokenCountingCallback
    ) -> tuple[list[CheckResult], dict[str, object]]:
        """Drive each turn with the prior turns injected as history.

        Returns the concatenated per-turn check results and the final turn's state
        (whose response/SQL the CaseResult reports — for a follow-up case that is the
        follow-up itself, i.e. "did memory make the follow-up resolve").
        """
        history: list[BaseMessage] = []
        check_results: list[CheckResult] = []
        state_dict: dict[str, object] = {}
        for turn in _case_turns(case):
            graph = self._graph_factory(collector)
            raw = graph.invoke(  # pyright: ignore[reportUnknownMemberType]
                cast(ChatState, {"question": turn.question, "history": list(history)}),
                config={"callbacks": [callback]},
            )
            state = cast(ChatState, raw)
            state_dict = cast(dict[str, object], state)
            check_results.extend(check.evaluate(state) for check in turn.checks)
            response = str(state_dict.get("response", ""))
            history.extend([HumanMessage(content=turn.question), AIMessage(content=response)])
        return check_results, state_dict
