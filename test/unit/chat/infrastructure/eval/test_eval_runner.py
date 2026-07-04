"""Unit tests for EvalRunner using a fake graph factory."""

import threading
import time
from collections.abc import Mapping
from typing import Any, cast

import pytest

from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.eval.metrics import MetricsRecorder
from chat.infrastructure.eval.runner import EvalCase, EvalReport, EvalRunner, EvalTurn
from chat.infrastructure.graph.chat_state import ChatState
from shared.domain.value_objects.query_result import QueryResult


def _state_for(question: str, response: str) -> Mapping[str, object]:
    """Minimal successful ChatState mirroring the orchestrator–workers output.

    The real graph keeps ``sql_query``/``query_result`` local to each build_widget
    worker; only the aggregated ``widget_results`` channel reaches the top-level
    state, so faithful fakes must expose the SQL and rows there.
    """
    result = QueryResult(columns=["n"], rows=[(1,)], row_count=1)
    return cast(
        ChatState,
        {
            "question": question,
            "tables": [],
            "schema": "",
            "widget_results": [
                WidgetResult(widget_id="widget-0", title="A", result=result, sql="SELECT 1")
            ],
            "widget_patch_lines": [],
            "response": response,
        },
    )


class _BarrierGraph:
    """Fake graph whose invoke blocks on a shared barrier to force overlap.

    If cases run concurrently the barrier releases all parties; if they run
    sequentially the first wait() times out, raising BrokenBarrierError.
    """

    def __init__(self, barrier: threading.Barrier) -> None:
        self._barrier = barrier

    def invoke(self, state: Any, config: Any = None) -> Mapping[str, object]:
        """Rendezvous at the barrier, then return a successful state."""
        self._barrier.wait()
        return _state_for(state.get("question", ""), "ok")


class _PerQuestionDelayGraph:
    """Fake graph that sleeps per-question so earlier cases can finish last."""

    def __init__(self, delays: dict[str, float]) -> None:
        self._delays = delays

    def invoke(self, state: Any, config: Any = None) -> Mapping[str, object]:
        """Sleep the configured delay for this question, echoing it as response."""
        question = str(state.get("question", ""))
        time.sleep(self._delays.get(question, 0.0))
        return _state_for(question, question)


class _FakeGraph:
    """Fake compiled graph that returns a fixed ChatState without LangGraph."""

    def __init__(self, response: str = "42", *, raise_on_invoke: Exception | None = None) -> None:
        self._response = response
        self._raise = raise_on_invoke
        self.invoke_calls: list[tuple[Any, Any]] = []

    def invoke(self, state: Any, config: Any = None) -> Mapping[str, object]:
        """Return a fixed state or raise if configured to do so."""
        self.invoke_calls.append((state, config))
        if self._raise is not None:
            raise self._raise
        return _state_for(str(state.get("question", "")), self._response)


class TestEvalRunnerMultiTurn:
    """A case with follow-ups threads each prior turn into the next as history."""

    def test_follow_up_turn_receives_prior_turn_as_history(self) -> None:
        # arrange — one base turn plus one follow-up
        fake_graph = _FakeGraph(response="ans")
        runner = EvalRunner(graph_factory=lambda _r: fake_graph, model_name="test-model")
        case = EvalCase(
            id="c1",
            question="turn one",
            checks=[],
            follow_ups=[EvalTurn(question="turn two", checks=[])],
        )
        # act
        runner.run([case])
        # assert — turn 1 runs with empty history; turn 2 sees turn 1's Q + answer
        states = [state for state, _config in fake_graph.invoke_calls]
        assert states[0]["question"] == "turn one" and states[0]["history"] == []
        assert states[1]["question"] == "turn two"
        assert [m.content for m in states[1]["history"]] == ["turn one", "ans"]

    def test_single_turn_case_runs_with_empty_history(self) -> None:
        fake_graph = _FakeGraph()
        runner = EvalRunner(graph_factory=lambda _r: fake_graph, model_name="test-model")
        runner.run([EvalCase(id="c1", question="just one", checks=[])])
        assert [s["history"] for s, _c in fake_graph.invoke_calls] == [[]]


class TestEvalRunnerGraphFactory:
    """EvalRunner calls graph_factory once per case with a fresh MetricsRecorder."""

    def test_factory_called_once_per_case(self) -> None:
        """Factory is invoked exactly once for a single-case run."""
        # arrange
        recorders: list[MetricsRecorder] = []
        fake_graph = _FakeGraph()

        def factory(recorder: MetricsRecorder) -> _FakeGraph:
            recorders.append(recorder)
            return fake_graph

        runner = EvalRunner(graph_factory=factory, model_name="test-model")
        cases = [EvalCase(id="c1", question="How many?", checks=[])]
        # act
        runner.run(cases)
        # assert — one fresh recorder per case
        assert len(recorders) == 1

    def test_factory_receives_a_metrics_recorder(self) -> None:
        """Factory argument satisfies the MetricsRecorder protocol."""
        # arrange
        received: list[MetricsRecorder] = []

        def factory(recorder: MetricsRecorder) -> _FakeGraph:
            received.append(recorder)
            return _FakeGraph()

        runner = EvalRunner(graph_factory=factory, model_name="test-model")
        # act
        runner.run([EvalCase(id="c1", question="q", checks=[])])
        # assert
        assert isinstance(received[0], MetricsRecorder)

    def test_two_cases_receive_independent_recorders(self) -> None:
        """Each case gets its own recorder so metrics are isolated per case."""
        # arrange — each case must get its own fresh recorder for metrics isolation
        recorders: list[MetricsRecorder] = []

        def factory(recorder: MetricsRecorder) -> _FakeGraph:
            recorders.append(recorder)
            return _FakeGraph()

        runner = EvalRunner(graph_factory=factory, model_name="test-model")
        cases = [
            EvalCase(id="c1", question="q1", checks=[]),
            EvalCase(id="c2", question="q2", checks=[]),
        ]
        # act
        runner.run(cases)
        # assert — two distinct recorder instances
        assert len(recorders) == 2
        assert recorders[0] is not recorders[1]


class TestEvalRunnerReport:
    """EvalRunner.run() returns an EvalReport reflecting the factory's output."""

    def _runner_with_response(self, response: str) -> EvalRunner:
        return EvalRunner(
            graph_factory=lambda _recorder: _FakeGraph(response),
            model_name="test-model",
        )

    def test_report_has_correct_model_name(self) -> None:
        """EvalReport.model is set to the model_name passed at construction."""
        runner = self._runner_with_response("42")
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        assert report.model == "test-model"

    def test_report_contains_one_case_per_input(self) -> None:
        """One CaseResult is produced for each EvalCase in the input list."""
        runner = self._runner_with_response("42")
        cases = [
            EvalCase(id="c1", question="q1", checks=[]),
            EvalCase(id="c2", question="q2", checks=[]),
        ]
        report = runner.run(cases)
        assert len(report.cases) == 2
        assert {c.case_id for c in report.cases} == {"c1", "c2"}

    def test_case_result_captures_response(self) -> None:
        """CaseResult.response reflects the value returned by the graph."""
        runner = self._runner_with_response("the answer")
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        assert report.cases[0].response == "the answer"

    def test_returns_eval_report_instance(self) -> None:
        """Return type is EvalReport."""
        runner = self._runner_with_response("ok")
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        assert isinstance(report, EvalReport)

    def test_run_at_is_utc_iso_string(self) -> None:
        # kills run__mutmut_3 (run_at=None) and mutmut_11 (datetime.now(None) → no tz)
        runner = self._runner_with_response("ok")
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        assert report.run_at is not None
        assert "+00:00" in report.run_at

    def test_summary_is_not_none(self) -> None:
        # kills run__mutmut_5 (summary=None instead of compute_summary(...))
        runner = self._runner_with_response("ok")
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        assert report.summary is not None
        assert isinstance(report.summary, dict)


class TestEvalRunnerErrorHandling:
    """Graph exceptions are captured per-case; the run continues."""

    def test_graph_exception_captured_in_case_error_field(self) -> None:
        """An exception from graph.invoke() is stored in CaseResult.error."""

        # arrange — graph raises unexpectedly
        def factory(_recorder: MetricsRecorder) -> _FakeGraph:
            return _FakeGraph(raise_on_invoke=RuntimeError("LLM timeout"))

        runner = EvalRunner(graph_factory=factory, model_name="test-model")
        # act
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        # assert — error is captured, case is marked failed, run continues
        case = report.cases[0]
        assert case.passed is False
        assert "LLM timeout" in (case.error or "")

    def test_one_failing_case_does_not_abort_subsequent_cases(self) -> None:
        """A failing case does not prevent later cases from running."""
        # arrange — first call raises, second succeeds
        call_count = 0

        def factory(_recorder: MetricsRecorder) -> _FakeGraph:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeGraph(raise_on_invoke=RuntimeError("boom"))
            return _FakeGraph("ok")

        runner = EvalRunner(graph_factory=factory, model_name="test-model")
        cases = [
            EvalCase(id="c1", question="q1", checks=[]),
            EvalCase(id="c2", question="q2", checks=[]),
        ]
        # act
        report = runner.run(cases)
        # assert — both cases present; second one passed
        assert len(report.cases) == 2
        assert report.cases[1].passed is True

    def test_error_case_preserves_case_id_and_question(self) -> None:
        # kills mutmut_73 (case_id=None) and mutmut_74 (question=None) in error path
        runner = EvalRunner(
            graph_factory=lambda _: _FakeGraph(raise_on_invoke=RuntimeError("boom")),
            model_name="test-model",
        )
        report = runner.run([EvalCase(id="my-case", question="What?", checks=[])])
        case = report.cases[0]
        assert case.case_id == "my-case"
        assert case.question == "What?"

    def test_error_case_has_empty_string_defaults(self) -> None:
        # kills mutmut_76 (sql_query=None), mutmut_78 (response=None),
        # mutmut_93 (sql_query="XXXX"), mutmut_95 (response="XXXX")
        runner = EvalRunner(
            graph_factory=lambda _: _FakeGraph(raise_on_invoke=RuntimeError("boom")),
            model_name="test-model",
        )
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        case = report.cases[0]
        assert case.sql_query == ""
        assert case.response == ""

    def test_error_case_sql_valid_is_false(self) -> None:
        # kills mutmut_77 (sql_valid=None) and mutmut_94 (sql_valid=True)
        runner = EvalRunner(
            graph_factory=lambda _: _FakeGraph(raise_on_invoke=RuntimeError("boom")),
            model_name="test-model",
        )
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        assert report.cases[0].sql_valid is False

    def test_error_case_check_results_is_empty_list(self) -> None:
        # kills mutmut_79 (check_results=None)
        runner = EvalRunner(
            graph_factory=lambda _: _FakeGraph(raise_on_invoke=RuntimeError("boom")),
            model_name="test-model",
        )
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        assert report.cases[0].check_results == []

    def test_error_case_propagates_tags(self) -> None:
        # kills mutmut_92 (tags= field missing from error CaseResult)
        runner = EvalRunner(
            graph_factory=lambda _: _FakeGraph(raise_on_invoke=RuntimeError("boom")),
            model_name="test-model",
        )
        case = EvalCase(id="c1", question="q", checks=[], tags=["hard", "aggregation"])
        report = runner.run([case])
        assert report.cases[0].tags == ["hard", "aggregation"]


class TestEvalRunnerConcurrency:
    """max_workers > 1 runs cases through a bounded thread pool, order preserved."""

    def test_cases_run_concurrently_when_workers_allow(self) -> None:
        """Two cases rendezvous at a barrier, proving they execute in parallel."""
        # arrange — barrier needs both cases inside invoke() at once, else it times out
        barrier = threading.Barrier(2, timeout=3.0)
        runner = EvalRunner(
            graph_factory=lambda _recorder: _BarrierGraph(barrier),
            model_name="test-model",
            max_workers=2,
        )
        cases = [
            EvalCase(id="c1", question="q1", checks=[]),
            EvalCase(id="c2", question="q2", checks=[]),
        ]
        # act
        report = runner.run(cases)
        # assert — neither case hit a BrokenBarrierError, so they overlapped
        assert all(c.error is None for c in report.cases)
        assert {c.case_id for c in report.cases} == {"c1", "c2"}

    def test_results_keep_input_order_despite_completion_order(self) -> None:
        """The first case finishes last, yet results stay in input order."""
        # arrange — c0 sleeps longest, so c1/c2 complete before it
        graph = _PerQuestionDelayGraph({"q0": 0.06, "q1": 0.0, "q2": 0.0})
        runner = EvalRunner(
            graph_factory=lambda _recorder: graph,
            model_name="test-model",
            max_workers=3,
        )
        cases = [
            EvalCase(id="c0", question="q0", checks=[]),
            EvalCase(id="c1", question="q1", checks=[]),
            EvalCase(id="c2", question="q2", checks=[]),
        ]
        # act
        report = runner.run(cases)
        # assert — output order mirrors input order, not completion order
        assert [c.case_id for c in report.cases] == ["c0", "c1", "c2"]
        assert [c.response for c in report.cases] == ["q0", "q1", "q2"]


class TestEvalRunnerCaseResultFields:
    """CaseResult captures sql_query, sql_valid, check_results, tags, and passed."""

    def _runner(self, response: str = "42") -> EvalRunner:
        return EvalRunner(
            graph_factory=lambda _recorder: _FakeGraph(response),
            model_name="test-model",
        )

    def test_case_result_captures_sql_query(self) -> None:
        # arrange — _FakeGraph returns sql_query="SELECT 1"
        runner = self._runner()
        # act
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        # assert
        assert report.cases[0].sql_query == "SELECT 1"

    def test_case_result_captures_sql_valid_true(self) -> None:
        # arrange — _FakeGraph returns a query_result, so sql_valid should be True
        runner = self._runner()
        # act
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        # assert
        assert report.cases[0].sql_valid is True

    def test_case_result_propagates_tags(self) -> None:
        # arrange
        runner = self._runner()
        case = EvalCase(id="c1", question="q", checks=[], tags=["aggregation", "hard"])
        # act
        report = runner.run([case])
        # assert
        assert report.cases[0].tags == ["aggregation", "hard"]

    def test_check_receives_full_state_not_none(self) -> None:
        # kills _run_case__mutmut_30 (c.evaluate(None) instead of c.evaluate(state))
        received: list[object] = []

        class _StateCapture:
            def evaluate(self, state: object) -> dict[str, object]:
                received.append(state)
                return {"type": "t", "value": "", "passed": True, "reasoning": ""}

        runner = EvalRunner(
            graph_factory=lambda _recorder: _FakeGraph("ok"),
            model_name="test-model",
        )
        runner.run([EvalCase(id="c1", question="q", checks=[_StateCapture()])])  # type: ignore[list-item]
        assert len(received) == 1
        assert received[0] is not None
        # state must have "response" key (set by FakeGraph)
        assert cast(Any, received[0]).get("response") == "ok"

    def test_case_result_passed_true_when_all_checks_pass(self) -> None:
        # arrange — a check that always passes
        class _AlwaysPass:
            def evaluate(self, state: object) -> dict[str, object]:
                return {"type": "t", "value": "", "passed": True, "reasoning": ""}

        runner = EvalRunner(
            graph_factory=lambda _recorder: _FakeGraph(),
            model_name="test-model",
        )
        case = EvalCase(id="c1", question="q", checks=[_AlwaysPass()])  # type: ignore[list-item]
        # act
        report = runner.run([case])
        # assert
        assert report.cases[0].passed is True
        assert len(report.cases[0].check_results) == 1

    def test_case_result_passed_false_when_any_check_fails(self) -> None:
        # arrange
        class _AlwaysFail:
            def evaluate(self, state: object) -> dict[str, object]:
                return {"type": "t", "value": "", "passed": False, "reasoning": "failed"}

        runner = EvalRunner(
            graph_factory=lambda _recorder: _FakeGraph(),
            model_name="test-model",
        )
        case = EvalCase(id="c1", question="q", checks=[_AlwaysFail()])  # type: ignore[list-item]
        # act
        report = runner.run([case])
        # assert
        assert report.cases[0].passed is False


class TestEvalRunnerDefaults:
    """EvalRunner stores default parameter values as attributes."""

    def test_default_input_price_per_m_is_zero(self) -> None:
        # arrange — create without passing prices; mutmut_1 sets input_price_per_m=1.0
        runner = EvalRunner(
            graph_factory=lambda _recorder: _FakeGraph(),
            model_name="test-model",
        )
        # act / assert
        assert runner._input_price_per_m == 0.0

    def test_default_output_price_per_m_is_zero(self) -> None:
        # mutmut_2 sets output_price_per_m=1.0 as default
        runner = EvalRunner(
            graph_factory=lambda _recorder: _FakeGraph(),
            model_name="test-model",
        )
        assert runner._output_price_per_m == 0.0

    def test_default_max_workers_is_one(self) -> None:
        # mutmut_3 sets max_workers=2 as default
        runner = EvalRunner(
            graph_factory=lambda _recorder: _FakeGraph(),
            model_name="test-model",
        )
        assert runner._max_workers == 1


class TestEvalRunnerCaseResultQuestion:
    """CaseResult.question must match EvalCase.question (not None)."""

    def test_case_result_question_matches_input_question(self) -> None:
        # arrange — mutmut_32 sets question=None in CaseResult
        runner = EvalRunner(
            graph_factory=lambda _recorder: _FakeGraph(),
            model_name="test-model",
        )
        case = EvalCase(id="c1", question="How many films?", checks=[])
        # act
        report = runner.run([case])
        # assert — must propagate the question, not None
        assert report.cases[0].question == "How many films?"


class TestEvalRunnerCaseResultSqlQueryDefault:
    """CaseResult.sql_query is "" when graph returns no sql_query key."""

    def test_sql_query_defaults_to_empty_string_when_missing(self) -> None:
        # arrange — a graph that returns state without sql_query key
        class _NoSqlGraph:
            def invoke(self, state: Any, config: Any = None) -> Any:
                return cast(
                    ChatState,
                    {"question": "q", "response": "ok", "tables": [], "schema": ""},
                )

        runner = EvalRunner(
            graph_factory=lambda _recorder: _NoSqlGraph(),
            model_name="test-model",
        )
        case = EvalCase(id="c1", question="q", checks=[])
        # act
        report = runner.run([case])
        # assert — mutmut_52 gives "None" but correct gives ""
        assert report.cases[0].sql_query == ""


class TestEvalRunnerCaseResultResponseDefault:
    """CaseResult.response is "" when graph returns no response key."""

    def test_response_defaults_to_empty_string_when_missing(self) -> None:
        # kills mutmut_64 (default=None → str(None)="None"),
        # mutmut_66 (default omitted → None), mutmut_69 (default="XXXX")
        class _NoResponseGraph:
            def invoke(self, state: Any, config: Any = None) -> Any:
                return cast(
                    ChatState, {"question": "q", "sql_query": "", "tables": [], "schema": ""}
                )

        runner = EvalRunner(
            graph_factory=lambda _recorder: _NoResponseGraph(),
            model_name="test-model",
        )
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        assert report.cases[0].response == ""


class TestEvalRunnerPricing:
    """EvalRunner passes input and output price per M tokens to compute_summary."""

    def test_input_price_is_used_for_input_tokens(self) -> None:
        # kills run__mutmut_16 (swaps input/output prices) and
        # run__mutmut_17 (drops output_price arg — output defaults to 0)
        # Strategy: use 1M input tokens, 0 output tokens, price input @ $1/M, output @ $0/M
        def factory(recorder: MetricsRecorder) -> _FakeGraph:
            recorder.record_tokens("gen", 1_000_000, 0)
            return _FakeGraph()

        runner = EvalRunner(
            graph_factory=factory,
            model_name="test-model",
            input_price_per_m=1.0,
            output_price_per_m=0.0,
        )
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        # 1M input tokens × $1/M = $1.000000 cost
        assert report.summary["cost_usd"] == pytest.approx(1.0)

    def test_output_price_is_used_for_output_tokens(self) -> None:
        # kills run__mutmut_17 (drops output_price → output_price defaults to 0)
        def factory(recorder: MetricsRecorder) -> _FakeGraph:
            recorder.record_tokens("gen", 0, 1_000_000)
            return _FakeGraph()

        runner = EvalRunner(
            graph_factory=factory,
            model_name="test-model",
            input_price_per_m=0.0,
            output_price_per_m=2.0,
        )
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        # 1M output tokens × $2/M = $2.0 cost
        assert report.summary["cost_usd"] == pytest.approx(2.0)


class TestEvalRunnerNodeMetrics:
    """Metrics recorded into the factory's recorder flow into CaseResult.nodes."""

    def test_node_metrics_from_recorder_appear_in_case_result(self) -> None:
        """Latency set on the recorder before invoke() surfaces in CaseResult.nodes."""

        # arrange — factory records a latency before returning
        def factory(recorder: MetricsRecorder) -> _FakeGraph:
            recorder.set_node("generate_sql")
            recorder.record_latency("generate_sql", 1.23)
            return _FakeGraph()

        runner = EvalRunner(graph_factory=factory, model_name="test-model")
        # act
        report = runner.run([EvalCase(id="c1", question="q", checks=[])])
        # assert — metrics flow from recorder into CaseResult
        assert "generate_sql" in report.cases[0].nodes
        assert report.cases[0].nodes["generate_sql"].latency_s == 1.23
