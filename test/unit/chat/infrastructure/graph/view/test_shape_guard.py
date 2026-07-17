"""Tests for the deterministic view-shape guard (single-row charts, oversized pies, KPIs)."""

import json

from chat.infrastructure.graph.view.shape_guard import coerce_view_to_shape
from shared.domain.value_objects.query_result import QueryResult


def _chart_lines(props: dict[str, object], element_id: str = "chart") -> list[str]:
    """A two-line authored view: a ChartJs leaf plus its root-children reference."""
    element = {"type": "ChartJs", "props": props, "children": []}
    return [
        json.dumps({"op": "add", "path": f"/elements/{element_id}", "value": element}),
        json.dumps({"op": "add", "path": "/elements/root/children/-", "value": element_id}),
    ]


def _leaf(lines: list[str]) -> dict[str, object]:
    """The value dict of the sole element-defining patch in a coerced line list."""
    for line in lines:
        patch = json.loads(line)
        if patch["path"].startswith("/elements/") and not patch["path"].endswith("/children/-"):
            return patch["value"]
    raise AssertionError("no element patch found")


class TestSingleRowChartCoercion:
    def test_analysis_single_row_chart_becomes_a_datatable(self) -> None:
        result = QueryResult(columns=["state"], rows=[("SP",)], row_count=1)
        lines = _chart_lines({"kind": "bar", "labelColumn": "state", "valueColumns": []})

        out = coerce_view_to_shape(lines, "analysis", result)

        assert _leaf(out)["type"] == "DataTable"
        assert _leaf(out)["props"]["data"] == {"$state": "/result"}

    def test_metric_single_row_chart_becomes_a_kpistat_on_the_numeric_column(self) -> None:
        result = QueryResult(columns=["state", "customers"], rows=[("SP", 1200)], row_count=1)
        lines = _chart_lines({"kind": "bar", "labelColumn": "state", "valueColumns": ["customers"]})

        out = coerce_view_to_shape(lines, "metric", result)

        leaf = _leaf(out)
        assert leaf["type"] == "KpiStat"
        assert leaf["props"]["valueColumn"] == "customers"
        assert leaf["props"]["data"] == {"$state": "/result/rows"}

    def test_metric_single_row_label_only_falls_back_to_a_datatable(self) -> None:
        # No numeric column to headline → a one-row table is the safe representation.
        result = QueryResult(columns=["state"], rows=[("SP",)], row_count=1)
        lines = _chart_lines({"kind": "bar", "labelColumn": "state", "valueColumns": []})

        out = coerce_view_to_shape(lines, "metric", result)

        assert _leaf(out)["type"] == "DataTable"

    def test_boolean_column_is_not_treated_as_numeric(self) -> None:
        result = QueryResult(columns=["is_top"], rows=[(True,)], row_count=1)
        lines = _chart_lines({"kind": "bar", "labelColumn": "is_top", "valueColumns": []})

        out = coerce_view_to_shape(lines, "metric", result)

        assert _leaf(out)["type"] == "DataTable"

    def test_the_root_children_reference_is_preserved(self) -> None:
        result = QueryResult(columns=["state"], rows=[("SP",)], row_count=1)
        lines = _chart_lines({"kind": "bar"}, element_id="c0")

        out = coerce_view_to_shape(lines, "analysis", result)

        assert json.loads(out[1]) == {
            "op": "add",
            "path": "/elements/root/children/-",
            "value": "c0",
        }


class TestOversizedPieDowngrade:
    def test_pie_with_more_than_five_slices_becomes_a_bar(self) -> None:
        rows = [(f"c{i}", i) for i in range(6)]
        result = QueryResult(columns=["cat", "n"], rows=rows, row_count=6)
        lines = _chart_lines({"kind": "pie", "labelColumn": "cat", "valueColumns": ["n"]})

        out = coerce_view_to_shape(lines, "analysis", result)

        leaf = _leaf(out)
        assert leaf["type"] == "ChartJs" and leaf["props"]["kind"] == "bar"
        assert leaf["props"]["labelColumn"] == "cat"  # labels/series preserved

    def test_pie_with_five_slices_is_left_untouched(self) -> None:
        rows = [(f"c{i}", i) for i in range(5)]
        result = QueryResult(columns=["cat", "n"], rows=rows, row_count=5)
        lines = _chart_lines({"kind": "pie", "labelColumn": "cat", "valueColumns": ["n"]})

        out = coerce_view_to_shape(lines, "analysis", result)

        assert out == lines


class TestNonViolatingViewsUntouched:
    def test_multi_row_bar_chart_is_left_untouched(self) -> None:
        rows = [(f"c{i}", i) for i in range(4)]
        result = QueryResult(columns=["cat", "n"], rows=rows, row_count=4)
        lines = _chart_lines({"kind": "bar", "labelColumn": "cat", "valueColumns": ["n"]})

        out = coerce_view_to_shape(lines, "analysis", result)

        assert out == lines

    def test_single_row_kpistat_is_left_untouched(self) -> None:
        result = QueryResult(columns=["total"], rows=[(42,)], row_count=1)
        element = {"type": "KpiStat", "props": {"valueColumn": "total"}, "children": []}
        lines = [json.dumps({"op": "add", "path": "/elements/k", "value": element})]

        out = coerce_view_to_shape(lines, "metric", result)

        assert out == lines

    def test_multi_row_kpistat_becomes_a_datatable(self) -> None:
        result = QueryResult(columns=["cat", "n"], rows=[("a", 1), ("b", 2)], row_count=2)
        element = {"type": "KpiStat", "props": {"valueColumn": "n"}, "children": []}
        lines = [json.dumps({"op": "add", "path": "/elements/k", "value": element})]

        out = coerce_view_to_shape(lines, "analysis", result)

        assert _leaf(out)["type"] == "DataTable"


class TestCompositeAndMalformedInputsUntouched:
    def test_a_multi_element_view_is_left_untouched(self) -> None:
        # Two authored elements → the guard cannot reason about the shape, so it defers.
        result = QueryResult(columns=["state"], rows=[("SP",)], row_count=1)
        lines = [
            json.dumps({"op": "add", "path": "/elements/a", "value": {"type": "ChartJs"}}),
            json.dumps({"op": "add", "path": "/elements/b", "value": {"type": "ChartJs"}}),
        ]

        out = coerce_view_to_shape(lines, "analysis", result)

        assert out == lines

    def test_lines_without_a_typed_element_are_returned_unchanged(self) -> None:
        result = QueryResult(columns=["state"], rows=[("SP",)], row_count=1)
        lines = [json.dumps({"op": "add", "path": "/elements/root/children/-", "value": "x"})]

        out = coerce_view_to_shape(lines, "analysis", result)

        assert out == lines


class TestExplicitViewHintDefers:
    def test_an_explicit_chart_hint_is_honoured_over_the_shape_rule(self) -> None:
        # The user asked for a chart → the guard defers even on a single row (the user's wish wins).
        result = QueryResult(columns=["state"], rows=[("SP",)], row_count=1)
        lines = _chart_lines({"kind": "bar", "labelColumn": "state", "valueColumns": []})

        out = coerce_view_to_shape(lines, "analysis", result, view_hint="chart")

        assert out == lines
