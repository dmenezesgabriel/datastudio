import json
from typing import cast

from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.eval.checks import deserialize_check
from chat.infrastructure.eval.view_checks import (
    ChartFitCheck,
    TextAnswerCheck,
    ViewContainsCheck,
    VizRubricCheck,
    WidgetCountCheck,
)
from chat.infrastructure.graph.chat_state import ChatState
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine


def _view_line(element_id: str, element: dict[str, object]) -> str:
    return json.dumps({"op": "add", "path": f"/elements/{element_id}", "value": element})


def _chart(
    kind: str, label_column: str = "month", value_columns: list[str] | None = None
) -> dict[str, object]:
    return {
        "type": "ChartJs",
        "props": {
            "kind": kind,
            "labelColumn": label_column,
            "valueColumns": value_columns or ["revenue"],
            "data": {"$state": "/result/rows"},
        },
        "children": [],
    }


def _kpi(value_column: str = "total") -> dict[str, object]:
    return {
        "type": "KpiStat",
        "props": {
            "label": "Total",
            "valueColumn": value_column,
            "data": {"$state": "/result/rows"},
        },
        "children": [],
    }


def _widget(widget_id: str, result: QueryResult) -> WidgetResult:
    return WidgetResult(widget_id=widget_id, title="W", result=result, sql="SELECT 1")


def _state(patch_lines: list[str], widgets: list[WidgetResult]) -> ChatState:
    return cast(
        ChatState,
        {
            "question": "How does it look?",
            "widget_patch_lines": patch_lines,
            "widget_results": widgets,
        },
    )


def _rows(n: int, columns: list[str]) -> QueryResult:
    row = tuple(range(len(columns)))
    return QueryResult(columns=columns, rows=[row] * n, row_count=n)


class TestViewContainsCheckChartKind:
    """ViewContainsCheck can pin the ChartJs kind, not just the element type."""

    def test_passes_when_chart_kind_matches(self) -> None:
        # arrange — a line chart is present and a line chart is expected
        state = _state([_view_line("widget-0-c", _chart("line"))], [])
        # act
        result = ViewContainsCheck(element_type="ChartJs", chart_kind="line").evaluate(state)
        # assert
        assert result["passed"] is True
        assert result["value"] == "ChartJs:line"

    def test_fails_when_chart_kind_differs(self) -> None:
        # arrange — a bar chart is present but a line chart is expected
        state = _state([_view_line("widget-0-c", _chart("bar"))], [])
        # act
        result = ViewContainsCheck(element_type="ChartJs", chart_kind="line").evaluate(state)
        # assert
        assert result["passed"] is False
        assert "ChartJs:line" in result["reasoning"]

    def test_matches_element_type_only_when_no_kind_given(self) -> None:
        # arrange — kind unset: any ChartJs satisfies (regression on prior behaviour)
        state = _state([_view_line("widget-0-c", _chart("pie"))], [])
        # act / assert
        assert ViewContainsCheck(element_type="ChartJs").evaluate(state)["passed"] is True

    def test_no_match_when_chart_props_are_not_a_dict(self) -> None:
        # arrange — a malformed ChartJs element (props not a dict) can't satisfy a kind
        bad = {"type": "ChartJs", "props": "oops", "children": []}
        state = _state([_view_line("widget-0-c", bad)], [])
        # act / assert
        check = ViewContainsCheck(element_type="ChartJs", chart_kind="line")
        assert check.evaluate(state)["passed"] is False


class TestChartFitCheck:
    """ChartFitCheck flags data-shape anti-patterns on the authored view."""

    def test_fails_when_pie_has_more_than_five_slices(self) -> None:
        # arrange — a pie bound to a 6-category result is unreadable
        widget = _widget("widget-0", _rows(6, ["category", "revenue"]))
        state = _state([_view_line("widget-0-c", _chart("pie", "category"))], [widget])
        # act
        result = ChartFitCheck().evaluate(state)
        # assert
        assert result["passed"] is False
        assert "pie" in result["reasoning"]

    def test_passes_when_pie_has_five_slices(self) -> None:
        # arrange — exactly five slices is still acceptable
        widget = _widget("widget-0", _rows(5, ["category", "revenue"]))
        state = _state([_view_line("widget-0-c", _chart("pie", "category"))], [widget])
        # act / assert
        assert ChartFitCheck().evaluate(state)["passed"] is True

    def test_fails_when_kpi_bound_to_multi_row_result(self) -> None:
        # arrange — a KPI must summarise a single row
        widget = _widget("widget-0", _rows(3, ["total"]))
        state = _state([_view_line("widget-0-k", _kpi())], [widget])
        # act
        result = ChartFitCheck().evaluate(state)
        # assert
        assert result["passed"] is False
        assert "KpiStat" in result["reasoning"]

    def test_passes_for_a_bar_chart_with_many_categories(self) -> None:
        # arrange — bar handles many categories fine
        widget = _widget("widget-0", _rows(20, ["category", "revenue"]))
        state = _state([_view_line("widget-0-c", _chart("bar", "category"))], [widget])
        # act / assert
        assert ChartFitCheck().evaluate(state)["passed"] is True

    def test_passes_vacuously_when_no_results(self) -> None:
        # arrange — SQL-failure / narrative-only path
        state = _state([_view_line("widget-0-c", _chart("pie"))], [])
        # act / assert
        assert ChartFitCheck().evaluate(state)["passed"] is True

    def test_falls_back_to_sole_result_for_unnamespaced_id(self) -> None:
        # arrange — a single widget and a non-widget-prefixed element id still maps
        widget = _widget("widget-0", _rows(9, ["category", "revenue"]))
        state = _state([_view_line("chart-1", _chart("pie", "category"))], [widget])
        # act / assert
        assert ChartFitCheck().evaluate(state)["passed"] is False

    def test_ignores_non_element_child_reference_lines(self) -> None:
        # arrange — a "/elements/root/children/-" line carries a string, not an element;
        # ChartFitCheck must skip it rather than fault on it
        widget = _widget("widget-0", _rows(4, ["category", "revenue"]))
        child_ref = json.dumps(
            {"op": "add", "path": "/elements/root/children/-", "value": "widget-0-c"}
        )
        state = _state([child_ref, _view_line("widget-0-c", _chart("bar", "category"))], [widget])
        # act / assert
        assert ChartFitCheck().evaluate(state)["passed"] is True

    def test_skips_element_whose_widget_result_is_unresolvable(self) -> None:
        # arrange — two widgets (no sole-result fallback) and a pie bound to a third,
        # unknown widget id: its row count is unresolvable, so no fault can be raised
        widgets = [_widget("widget-0", _rows(2, ["v"])), _widget("widget-1", _rows(2, ["v"]))]
        state = _state([_view_line("widget-9-c", _chart("pie", "category"))], widgets)
        # act / assert
        assert ChartFitCheck().evaluate(state)["passed"] is True


class TestWidgetCountCheck:
    """WidgetCountCheck asserts the dashboard branch produced enough widgets."""

    def test_passes_when_widget_count_meets_minimum(self) -> None:
        # arrange — three widgets built, two required
        widgets = [_widget(f"widget-{i}", _rows(1, ["v"])) for i in range(3)]
        state = _state([], widgets)
        # act
        result = WidgetCountCheck(min_widgets=2).evaluate(state)
        # assert
        assert result["passed"] is True
        assert result["value"] == "2"

    def test_fails_when_below_minimum(self) -> None:
        # arrange — one widget built, two required (single-answer, not a dashboard)
        state = _state([], [_widget("widget-0", _rows(1, ["v"]))])
        # act
        result = WidgetCountCheck(min_widgets=2).evaluate(state)
        # assert
        assert result["passed"] is False
        assert "built 1 widget" in result["reasoning"]


class TestVizRubricCheck:
    """VizRubricCheck judges presentation choice, feeding the judge views + data shape."""

    def test_passes_and_reports_type_when_judge_approves(self) -> None:
        # arrange
        model = FakeStructuredChatModel(passed=True, reasoning="Line fits the monthly trend")
        widget = _widget("widget-0", _rows(12, ["month", "avg_high"]))
        state = _state([_view_line("widget-0-c", _chart("line", "month"))], [widget])
        # act
        result = VizRubricCheck(model, rubric="A monthly trend should be a line chart.").evaluate(
            state
        )
        # assert
        assert result["passed"] is True
        assert result["type"] == "viz_rubric"
        assert result["reasoning"] == "Line fits the monthly trend"

    def test_feeds_question_views_and_data_shape_to_judge(self) -> None:
        # arrange
        model = FakeStructuredChatModel(passed=True, reasoning="")
        widget = _widget("widget-0", _rows(12, ["month", "avg_high"]))
        state = _state([_view_line("widget-0-c", _chart("line", "month"))], [widget])
        # act
        VizRubricCheck(model, rubric="Trend should be a line.").evaluate(state)
        # assert — the judge sees the chart kind, the columns, and the row count
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "kind=line" in combined
        assert "month" in combined
        assert "rows=12" in combined


class TestTextAnswerCheck:
    def _state(self, response: str, widgets: list[WidgetResult]) -> ChatState:
        return cast(ChatState, {"question": "hi", "response": response, "widget_results": widgets})

    def test_passes_for_a_text_only_answer(self) -> None:
        result = TextAnswerCheck().evaluate(self._state("I can query your data.", []))
        assert result["passed"] is True

    def test_fails_when_a_widget_was_built(self) -> None:
        widget = _widget("widget-0", _rows(1, ["n"]))
        result = TextAnswerCheck().evaluate(self._state("42 orders.", [widget]))
        assert result["passed"] is False
        assert "widget" in result["reasoning"]

    def test_fails_when_there_is_no_response(self) -> None:
        result = TextAnswerCheck().evaluate(self._state("   ", []))
        assert result["passed"] is False


class TestDeserializeNewCheckTypes:
    def _deserialize(self, spec: dict[str, str]) -> object:
        return deserialize_check(
            spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
        )

    def test_builds_view_contains_with_chart_kind(self) -> None:
        # arrange / act
        check = self._deserialize(
            {"type": "view_contains", "element_type": "ChartJs", "chart_kind": "line"}
        )
        # assert
        assert isinstance(check, ViewContainsCheck)
        assert check.chart_kind == "line"

    def test_view_contains_chart_kind_defaults_to_none(self) -> None:
        check = self._deserialize({"type": "view_contains", "element_type": "KpiStat"})
        assert isinstance(check, ViewContainsCheck)
        assert check.chart_kind is None

    def test_builds_chart_fit_check(self) -> None:
        assert isinstance(self._deserialize({"type": "chart_fit"}), ChartFitCheck)

    def test_builds_widget_count_check(self) -> None:
        check = self._deserialize({"type": "widget_count", "min_widgets": "2"})
        assert isinstance(check, WidgetCountCheck)
        assert check.min_widgets == 2

    def test_builds_viz_rubric_check(self) -> None:
        check = self._deserialize({"type": "viz_rubric", "rubric": "Trend should be a line."})
        assert isinstance(check, VizRubricCheck)
        assert check.rubric == "Trend should be a line."

    def test_builds_text_answer_check(self) -> None:
        assert isinstance(self._deserialize({"type": "text_answer"}), TextAnswerCheck)
