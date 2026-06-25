"""Unit tests for EvalRunner using a fake graph factory."""

from collections.abc import Mapping
from typing import Any, cast

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.eval.metrics import MetricsRecorder
from chat.infrastructure.eval.runner import EvalCase, EvalReport, EvalRunner
from shared.domain.value_objects.query_result import QueryResult


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
        return cast(
            ChatState,
            {
                "question": state.get("question", ""),
                "tables": [],
                "schema": "",
                "sql_query": "SELECT 1",
                "sql_error": "",
                "query_result": QueryResult(columns=["n"], rows=[(1,)], row_count=1),
                "response": self._response,
            },
        )


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
