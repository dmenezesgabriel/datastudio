import datetime
from dataclasses import dataclass
from typing import cast

from langchain_core.language_models import BaseChatModel

from shared.application.ports.sql_engine_port import SqlEnginePort
from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.eval.checks import Check, CheckResult
from chat.infrastructure.eval.graph_builder import build_eval_graph
from chat.infrastructure.eval.metrics import EvalCollector, NodeMetrics
from chat.infrastructure.eval.token_callback import TokenCountingCallback


@dataclass
class EvalCase:
    """A single evaluation case: a question plus a set of correctness checks."""

    id: str
    question: str
    checks: list[Check]


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


@dataclass
class EvalReport:
    """Full eval run report, ready for JSON serialisation via dataclasses.asdict."""

    run_at: str
    model: str
    summary: dict[str, object]
    cases: list[CaseResult]


def _compute_summary(cases: list[CaseResult]) -> dict[str, object]:
    total = len(cases)
    passed = sum(1 for c in cases if c.passed)
    latencies = [sum(m.latency_s for m in c.nodes.values()) for c in cases]
    avg_latency = sum(latencies) / total if total else 0.0
    input_tokens = sum((m.input_tokens or 0) for c in cases for m in c.nodes.values())
    output_tokens = sum((m.output_tokens or 0) for c in cases for m in c.nodes.values())
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "avg_latency_s": round(avg_latency, 3),
        "total_input_tokens": input_tokens,
        "total_output_tokens": output_tokens,
    }


class EvalRunner:
    """Runs EvalCases through the instrumented graph and returns an EvalReport.

    The judge model for RubricCheck is already baked into the Check objects at
    deserialisation time, so this class only drives the text2sql pipeline.

    Example:
        runner = EvalRunner(chat_model, sql_engine, "openai/glm-5")
        report = runner.run(cases)
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        sql_engine: SqlEnginePort,
        model_name: str,
    ) -> None:
        self._chat_model = chat_model
        self._sql_engine = sql_engine
        self._model_name = model_name

    def run(self, cases: list[EvalCase]) -> EvalReport:
        """Run all cases sequentially and return a consolidated report."""
        results = [self._run_case(case) for case in cases]
        return EvalReport(
            run_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            model=self._model_name,
            summary=_compute_summary(results),
            cases=results,
        )

    def _run_case(self, case: EvalCase) -> CaseResult:
        collector = EvalCollector()
        graph = build_eval_graph(self._chat_model, self._sql_engine, collector)
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
            )
