"""Tests for per-widget view authoring: validation, fallback, and namespacing."""

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from chat.infrastructure.graph.nodes.generate_widget_view import (
    GenerateWidgetView,
    keep_valid_patch_lines,
    namespace_widget_patches,
)
from chat.infrastructure.graph.response_content_extractor import PlainTextExtractor
from shared.domain.value_objects.query_result import QueryResult


class FakeViewModel:
    def __init__(self, content: object) -> None:
        self._content = content
        self.received: list[BaseMessage] = []

    def with_config(self, *args: Any, **kwargs: Any) -> "FakeViewModel":
        """Honor the Runnable surface; the fake replays a fixed content regardless."""
        return self

    def invoke(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> AIMessage:
        self.received = messages
        return AIMessage(content=self._content)  # type: ignore[arg-type]


def _result() -> QueryResult:
    return QueryResult(columns=["month", "revenue"], rows=[("Jan", 100)], row_count=1)


class TestValidViewPatchLines:
    def test_keeps_add_patches_drops_prose_and_reserved(self) -> None:
        text = (
            "Here you go:\n"
            '{"op":"add","path":"/elements/chart","value":{"type":"ChartJs"}}\n'
            '{"op":"replace","path":"/elements/narrative/props/text","value":"x"}\n'
            '{"op":"add","path":"/elements/root/children/-","value":"chart"}'
        )
        assert keep_valid_patch_lines(text) == [
            '{"op":"add","path":"/elements/chart","value":{"type":"ChartJs"}}',
            '{"op":"add","path":"/elements/root/children/-","value":"chart"}',
        ]


class TestNamespaceWidgetPatches:
    def test_prefixes_element_ids_and_routes_an_analysis_widget_into_the_grid(self) -> None:
        lines = [
            json.dumps({"op": "add", "path": "/elements/chart", "value": {"type": "ChartJs"}}),
            json.dumps({"op": "add", "path": "/elements/root/children/-", "value": "chart"}),
        ]
        out = [json.loads(line) for line in namespace_widget_patches(lines, "widget-0", "analysis")]
        assert out[0]["path"] == "/elements/widget-0-chart"
        # the leaf is wrapped in a WidgetFrame (carrying its SQL) placed in the grid region
        assert out[1] == {
            "op": "add",
            "path": "/elements/widget-0-frame",
            "value": {
                "type": "WidgetFrame",
                "props": {"sql": ""},
                "children": ["widget-0-chart"],
            },
        }
        assert out[2] == {
            "op": "add",
            "path": "/elements/grid/children/-",
            "value": "widget-0-frame",
        }

    def test_routes_a_metric_widget_into_the_headline_band(self) -> None:
        lines = [
            json.dumps({"op": "add", "path": "/elements/k", "value": {"type": "KpiStat"}}),
            json.dumps({"op": "add", "path": "/elements/root/children/-", "value": "k"}),
        ]
        out = [json.loads(line) for line in namespace_widget_patches(lines, "widget-3", "metric")]
        assert out[2] == {
            "op": "add",
            "path": "/elements/kpi-row/children/-",
            "value": "widget-3-frame",
        }

    def test_region_follows_role_not_the_authored_element(self) -> None:
        # The fix: placement is driven by the declared role, never sniffed from the element.
        # A metric widget lands in the KPI band even if the leaf isn't (yet) a KpiStat, and an
        # analysis widget stays in the grid even when the model authored a KpiStat.
        kpi_leaf = [
            json.dumps({"op": "add", "path": "/elements/k", "value": {"type": "KpiStat"}}),
            json.dumps({"op": "add", "path": "/elements/root/children/-", "value": "k"}),
        ]
        table_leaf = [
            json.dumps({"op": "add", "path": "/elements/t", "value": {"type": "DataTable"}}),
            json.dumps({"op": "add", "path": "/elements/root/children/-", "value": "t"}),
        ]

        def region_of(lines: list[str], widget_id: str, role: str) -> str:
            out = [json.loads(line) for line in namespace_widget_patches(lines, widget_id, role)]
            placement = next(p for p in out if p["path"].endswith("/children/-"))
            return placement["path"]

        assert region_of(table_leaf, "widget-0", "metric") == "/elements/kpi-row/children/-"
        assert region_of(kpi_leaf, "widget-1", "analysis") == "/elements/grid/children/-"

    def test_rewrites_state_binding_to_widget_path(self) -> None:
        element = {
            "type": "ChartJs",
            "props": {"data": {"$state": "/result/rows"}, "labelColumn": "month"},
            "children": [],
        }
        line = json.dumps({"op": "add", "path": "/elements/c", "value": element})
        out = json.loads(namespace_widget_patches([line], "widget-2", "analysis")[0])
        assert out["value"]["props"]["data"] == {"$state": "/widget-2/rows"}
        assert out["value"]["props"]["labelColumn"] == "month"  # untouched

    def test_rewrites_bare_result_binding(self) -> None:
        element = {"type": "DataTable", "props": {"data": {"$state": "/result"}}, "children": []}
        line = json.dumps({"op": "add", "path": "/elements/t", "value": element})
        out = json.loads(namespace_widget_patches([line], "widget-1", "analysis")[0])
        assert out["value"]["props"]["data"] == {"$state": "/widget-1"}


class TestGenerateWidgetView:
    def test_authors_namespaced_lines_from_model(self) -> None:
        content = (
            '{"op":"add","path":"/elements/chart","value":'
            '{"type":"ChartJs","props":{"data":{"$state":"/result/rows"}},"children":[]}}\n'
            '{"op":"add","path":"/elements/root/children/-","value":"chart"}'
        )
        node = GenerateWidgetView(FakeViewModel(content), "prompt", PlainTextExtractor())  # type: ignore[arg-type]
        lines = node.author("widget-0", "Revenue", "analysis", _result())
        assert json.loads(lines[0])["path"] == "/elements/widget-0-chart"
        assert json.loads(lines[0])["value"]["props"]["data"] == {"$state": "/widget-0/rows"}
        # the leaf is wrapped in a frame (lines[1]) that is placed in its region (lines[2])
        assert json.loads(lines[1])["value"]["type"] == "WidgetFrame"
        assert json.loads(lines[2])["value"] == "widget-0-frame"

    def test_falls_back_to_namespaced_data_table(self) -> None:
        node = GenerateWidgetView(FakeViewModel("sorry"), "prompt", PlainTextExtractor())  # type: ignore[arg-type]
        lines = [json.loads(line) for line in node.author("widget-3", "T", "analysis", _result())]
        table = next(p for p in lines if p["path"].startswith("/elements/widget-3-"))
        assert table["value"]["type"] == "DataTable"
        assert table["value"]["props"]["data"] == {"$state": "/widget-3"}

    def test_prompt_has_title_and_schema_not_values(self) -> None:
        model = FakeViewModel('{"op":"add","path":"/elements/x","value":{"type":"KpiStat"}}')
        GenerateWidgetView(model, "prompt", PlainTextExtractor()).author(
            "widget-0", "Revenue title", "analysis", _result()
        )  # type: ignore[arg-type]
        human = str(model.received[-1].content)
        assert "Revenue title" in human and "month" in human and "number" in human
        assert "Jan" not in human and "100" not in human

    def test_metric_role_prompt_mandates_a_kpistat(self) -> None:
        # A metric widget is a headline number → the worker is told to author a KpiStat,
        # so the KPI band the host already reserved is actually filled.
        model = FakeViewModel('{"op":"add","path":"/elements/x","value":{"type":"KpiStat"}}')
        GenerateWidgetView(model, "prompt", PlainTextExtractor()).author(
            "widget-0", "Total revenue", "metric", _result()
        )  # type: ignore[arg-type]
        human = str(model.received[-1].content)
        assert "KpiStat" in human and "valueColumn" in human


class TestExplicitViewHint:
    """An explicit view_hint overrides the data-shape default and mandates a component."""

    def test_table_hint_mandates_a_datatable(self) -> None:
        # The user asked for a table → the worker is told to author a DataTable, even though
        # a two-column result would otherwise suggest a chart.
        model = FakeViewModel('{"op":"add","path":"/elements/x","value":{"type":"DataTable"}}')
        GenerateWidgetView(model, "prompt", PlainTextExtractor()).author(
            "widget-0", "Orders by status", "analysis", _result(), "table"
        )  # type: ignore[arg-type]
        human = str(model.received[-1].content)
        assert "DataTable" in human and "TABLE" in human

    def test_hint_overrides_metric_role_guidance(self) -> None:
        # A chart hint wins over the role's default KpiStat guidance.
        model = FakeViewModel('{"op":"add","path":"/elements/x","value":{"type":"ChartJs"}}')
        GenerateWidgetView(model, "prompt", PlainTextExtractor()).author(
            "widget-0", "Total", "metric", _result(), "chart"
        )  # type: ignore[arg-type]
        human = str(model.received[-1].content)
        assert "CHART" in human and "ChartJs" in human

    def test_no_hint_leaves_role_guidance_unchanged(self) -> None:
        # Without a hint an analysis widget keeps its data-shape choice (ChartJs vs DataTable).
        model = FakeViewModel('{"op":"add","path":"/elements/x","value":{"type":"ChartJs"}}')
        GenerateWidgetView(model, "prompt", PlainTextExtractor()).author(
            "widget-0", "Trend", "analysis", _result()
        )  # type: ignore[arg-type]
        human = str(model.received[-1].content)
        assert "ChartJs" in human and "DataTable" in human

    def test_analysis_guidance_forbids_charting_a_single_row(self) -> None:
        # A single-row analysis result is a headline answer → the worker is told not to chart it.
        model = FakeViewModel('{"op":"add","path":"/elements/x","value":{"type":"KpiStat"}}')
        GenerateWidgetView(model, "prompt", PlainTextExtractor()).author(
            "widget-0", "Top state", "analysis", _result()
        )  # type: ignore[arg-type]
        human = str(model.received[-1].content)
        assert "SINGLE row" in human and "never chart it" in human
