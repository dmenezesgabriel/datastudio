"""Eval runner: orchestrates EvalCases through the instrumented graph."""

import datetime
import math
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Literal, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from chat.domain.value_objects.render_tree import RenderTree
from chat.infrastructure.eval._check_base import patch_lines, widget_results
from chat.infrastructure.eval.checks import Check, CheckResult
from chat.infrastructure.eval.metrics import EvalCollector, MetricsRecorder, NodeMetrics
from chat.infrastructure.eval.token_callback import TokenCountingCallback
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.types import TypedChatGraph
from chat.infrastructure.graph.view.render_tree_builder import (
    apply_patch_lines,
    compile_render_tree,
)


@dataclass
class EvalTurn:
    """One turn within a case: a build question or an edit instruction, plus its checks.

    A turn is a *build* turn (``question`` set) that drives the text2sql graph, or an *edit*
    turn (``instruction`` set) that reopens the prior turn's dashboard and drives the edit
    graph. Follow-up turns are also how short-term memory is graded: a turn whose question
    only resolves against prior turns (e.g. "now break it down by month") passes only when
    the accumulated conversation history reaches the graph.
    """

    question: str = ""
    checks: list[Check] = field(default_factory=list[Check])
    instruction: str | None = None

    @property
    def is_edit(self) -> bool:
        """True when this turn edits the prior dashboard rather than asking a new question."""
        return bool(self.instruction)


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
    """Outcome of running one EvalCase through the instrumented graph.

    ``attempt`` is the 0-based repetition index: when the runner repeats a case k times
    the report holds k CaseResults per ``case_id``, aggregated into a CaseConsistency.
    """

    case_id: str
    question: str
    nodes: dict[str, NodeMetrics]
    sql: str
    sql_valid: bool
    narrative: str
    check_results: list[CheckResult]
    passed: bool
    error: str | None
    tags: list[str] = field(default_factory=list[str])
    attempt: int = 0


@dataclass
class CaseConsistency:
    """A case's pass@k reliability across its repeated attempts.

    ``consistency`` is the fraction of attempts that fully passed; ``flaky`` marks a case
    that neither always passes nor always fails (0 < consistency < 1) — the signal a single
    run cannot surface. A case clears the SLO gate when consistency ≥ the configured floor.
    """

    case_id: str
    attempts: int
    passed_count: int
    consistency: float
    flaky: bool


@dataclass
class EvalReport:
    """Full eval run report, ready for JSON serialisation via dataclasses.asdict."""

    run_at: str
    model: str
    summary: dict[str, object]
    cases: list[CaseResult]
    consistency: list[CaseConsistency] = field(default_factory=list[CaseConsistency])


def _case_turns(case: EvalCase) -> list[EvalTurn]:
    """The case as an ordered turn list: the base question then any follow-ups."""
    return [EvalTurn(case.question, case.checks), *case.follow_ups]


def _compile_prior_spec(build_state: dict[str, object]) -> RenderTree:
    """Compile a completed build turn's state into the RenderTree an edit turn reopens.

    Mirrors the sync/CLI view path: the widgets' SpecStream patch lines plus each widget's
    SQL are compiled into the same F-layout dashboard the frontend would render, so the edit
    graph sees a faithful prior dashboard rather than raw graph state.
    """
    state = cast(ChatState, build_state)
    sql_by_widget = {w.widget_id: w.sql for w in widget_results(state)}
    return compile_render_tree(
        str(build_state.get("narrative", "")), patch_lines(state), sql_by_widget
    )


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


def aggregate_consistency(cases: list[CaseResult]) -> list[CaseConsistency]:
    """Collapse per-attempt CaseResults into one CaseConsistency per case id, in first-seen order.

    Example:
        aggregate_consistency([r_pass, r_fail])  # → [CaseConsistency(consistency=0.5, flaky=True)]
    """
    outcomes: dict[str, list[bool]] = {}
    for case in cases:
        outcomes.setdefault(case.case_id, []).append(case.passed)
    records: list[CaseConsistency] = []
    for case_id, passes in outcomes.items():
        attempts, passed = len(passes), sum(passes)
        rate = passed / attempts if attempts else 0.0
        records.append(
            CaseConsistency(case_id, attempts, passed, round(rate, 3), 0 < passed < attempts)
        )
    return records


def _consistency_summary(records: list[CaseConsistency]) -> dict[str, object]:
    """Mean consistency plus counts of reliable (=1.0) / flaky / always-failing cases."""
    total = len(records)
    mean = sum(r.consistency for r in records) / total if total else 0.0
    return {
        "cases": total,
        "mean_consistency": round(mean, 3),
        "reliable": sum(1 for r in records if r.passed_count == r.attempts and r.attempts > 0),
        "flaky": sum(1 for r in records if r.flaky),
        "failing": sum(1 for r in records if r.passed_count == 0),
    }


# The checks that grade "did the agent choose the right response shape" (text vs KPI vs
# chart vs table vs dashboard) — as opposed to structural/data-correctness checks. Their
# aggregate accuracy is surfaced as a headline metric so response-type selection is
# visible without slicing per-tag.
_VIEW_SELECTION_CHECKS = frozenset(
    {
        "view_present",
        "view_contains",
        "chart_fit",
        "kpi_band_populated",
        "viz_rubric",
        "widget_count",
        "text_answer",
    }
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
        "consistency": _consistency_summary(aggregate_consistency(cases)),
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
        repeats: int = 1,
        edit_graph_factory: Callable[[MetricsRecorder], TypedChatGraph] | None = None,
    ) -> None:
        """Store the factories, pricing, concurrency, and repetition; graphs build per attempt.

        max_workers > 1 runs attempts through a bounded thread pool. Each attempt
        already gets its own graph + collector, and the SqlEnginePort opens a
        fresh read-only connection per call, so attempts are isolated — keep the
        bound modest since the real ceiling is upstream LLM rate limits. ``repeats``
        runs every case that many times so per-case consistency (pass@k) is measurable.
        ``edit_graph_factory`` builds the dashboard-edit graph an edit turn drives; it is
        required only when a case includes an edit turn.
        """
        self._graph_factory = graph_factory
        self._edit_graph_factory = edit_graph_factory
        self._model_name = model_name
        self._input_price_per_m = input_price_per_m
        self._output_price_per_m = output_price_per_m
        self._max_workers = max_workers
        self._repeats = repeats

    def run(self, cases: list[EvalCase]) -> EvalReport:
        """Run all cases (each ``repeats`` times) and return a consolidated report."""
        results = self._run_cases(cases)
        return EvalReport(
            run_at=datetime.datetime.now(datetime.UTC).isoformat(),
            model=self._model_name,
            summary=compute_summary(results, self._input_price_per_m, self._output_price_per_m),
            cases=results,
            consistency=aggregate_consistency(results),
        )

    def _run_cases(self, cases: list[EvalCase]) -> list[CaseResult]:
        """Run every case ``repeats`` times, sequentially or via a thread pool.

        Results keep input order in both paths (attempts of a case stay adjacent, and
        ThreadPoolExecutor.map preserves ordering), so the report is deterministic
        regardless of completion order.
        """
        attempts = [(case, k) for case in cases for k in range(self._repeats)]
        if self._max_workers <= 1:
            return [self._run_attempt(item) for item in attempts]
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            return list(pool.map(self._run_attempt, attempts))

    def _run_attempt(self, item: tuple[EvalCase, int]) -> CaseResult:
        """Run one repetition of a case, stamping the CaseResult with its attempt index."""
        case, attempt = item
        result = self._run_case(case)
        result.attempt = attempt
        return result

    def _run_case(self, case: EvalCase) -> CaseResult:
        # One collector spans all turns so node latency/tokens reflect the whole
        # conversation — a follow-up's injected history shows up as extra input tokens.
        collector = EvalCollector()
        callback = TokenCountingCallback(collector)
        try:
            check_results, state_dict = self._run_turns(case, collector, callback)
            results = widget_results(cast(ChatState, state_dict))
            return CaseResult(
                case_id=case.id,
                question=case.question,
                nodes=collector.node_metrics,
                sql="; ".join(r.sql for r in results),
                sql_valid=bool(results),
                narrative=str(state_dict.get("narrative", "")),
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
                sql="",
                sql_valid=False,
                narrative="",
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
        prior_build: dict[str, object] | None = None
        for turn in _case_turns(case):
            if turn.is_edit:
                state_dict = self._run_edit_turn(turn, prior_build, collector, callback, history)
            else:
                state_dict = self._run_build_turn(turn, collector, callback, history)
                prior_build = state_dict
            check_results.extend(
                check.evaluate(cast(ChatState, state_dict)) for check in turn.checks
            )
            prompt = turn.instruction or turn.question
            history.extend(
                [
                    HumanMessage(content=prompt),
                    AIMessage(content=str(state_dict.get("narrative", ""))),
                ]
            )
        return check_results, state_dict

    def _run_build_turn(
        self,
        turn: EvalTurn,
        collector: MetricsRecorder,
        callback: TokenCountingCallback,
        history: list[BaseMessage],
    ) -> dict[str, object]:
        """Drive the text2sql graph for a question turn and return its final state."""
        graph = self._graph_factory(collector)
        final_state = graph.invoke(  # pyright: ignore[reportUnknownMemberType]
            cast(ChatState, {"question": turn.question, "history": list(history)}),
            config={"callbacks": [callback]},
        )
        return cast(dict[str, object], final_state)

    def _run_edit_turn(
        self,
        turn: EvalTurn,
        prior_build: dict[str, object] | None,
        collector: MetricsRecorder,
        callback: TokenCountingCallback,
        history: list[BaseMessage],
    ) -> dict[str, object]:
        """Drive the edit graph against the prior turn's dashboard, grading the edited spec.

        Compiles the prior build turn into a RenderTree, runs the edit graph with that as
        ``prior_spec``, applies the emitted patches, and stashes the resulting tree under
        ``edited_spec`` so the edit checks can grade the merged dashboard (not raw patches).
        """
        if self._edit_graph_factory is None:
            raise ValueError("edit turn requires an edit_graph_factory; none was provided")
        if prior_build is None:
            raise ValueError("edit turn has no prior build turn to seed prior_spec from")
        prior_spec = _compile_prior_spec(prior_build)
        graph = self._edit_graph_factory(collector)
        edit_state = graph.invoke(  # pyright: ignore[reportUnknownMemberType]
            cast(
                ChatState,
                {
                    "instruction": turn.instruction,
                    "prior_spec": prior_spec,
                    "history": list(history),
                },
            ),
            config={"callbacks": [callback]},
        )
        edit_dict = cast(dict[str, object], edit_state)
        edit_dict["prior_spec"] = prior_spec
        edit_dict["edited_spec"] = apply_patch_lines(
            prior_spec, patch_lines(cast(ChatState, edit_dict))
        )
        return edit_dict
