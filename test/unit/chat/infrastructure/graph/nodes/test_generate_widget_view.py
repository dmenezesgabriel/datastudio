"""Tests for per-widget view authoring: validation, fallback, and namespacing."""

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from chat.infrastructure.graph.nodes.generate_widget_view import (
    GenerateWidgetView,
    namespace_widget_patches,
    valid_view_patch_lines,
)
from chat.infrastructure.graph.plain_text_extractor import PlainTextExtractor
from shared.domain.value_objects.query_result import QueryResult


class FakeViewModel:
    def __init__(self, content: object) -> None:
        self._content = content
        self.received: list[BaseMessage] = []

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
        assert valid_view_patch_lines(text) == [
            '{"op":"add","path":"/elements/chart","value":{"type":"ChartJs"}}',
            '{"op":"add","path":"/elements/root/children/-","value":"chart"}',
        ]


class TestNamespaceWidgetPatches:
    def test_prefixes_element_ids_and_child_refs(self) -> None:
        lines = [
            json.dumps({"op": "add", "path": "/elements/chart", "value": {"type": "ChartJs"}}),
            json.dumps({"op": "add", "path": "/elements/root/children/-", "value": "chart"}),
        ]
        out = [json.loads(line) for line in namespace_widget_patches(lines, "widget-0")]
        assert out[0]["path"] == "/elements/widget-0-chart"
        assert out[1] == {
            "op": "add",
            "path": "/elements/root/children/-",
            "value": "widget-0-chart",
        }

    def test_rewrites_state_binding_to_widget_path(self) -> None:
        element = {
            "type": "ChartJs",
            "props": {"data": {"$state": "/result/rows"}, "labelColumn": "month"},
            "children": [],
        }
        line = json.dumps({"op": "add", "path": "/elements/c", "value": element})
        out = json.loads(namespace_widget_patches([line], "widget-2")[0])
        assert out["value"]["props"]["data"] == {"$state": "/widget-2/rows"}
        assert out["value"]["props"]["labelColumn"] == "month"  # untouched

    def test_rewrites_bare_result_binding(self) -> None:
        element = {"type": "DataTable", "props": {"data": {"$state": "/result"}}, "children": []}
        line = json.dumps({"op": "add", "path": "/elements/t", "value": element})
        out = json.loads(namespace_widget_patches([line], "widget-1")[0])
        assert out["value"]["props"]["data"] == {"$state": "/widget-1"}


class TestGenerateWidgetView:
    def test_authors_namespaced_lines_from_model(self) -> None:
        content = (
            '{"op":"add","path":"/elements/chart","value":'
            '{"type":"ChartJs","props":{"data":{"$state":"/result/rows"}},"children":[]}}\n'
            '{"op":"add","path":"/elements/root/children/-","value":"chart"}'
        )
        node = GenerateWidgetView(FakeViewModel(content), "prompt", PlainTextExtractor())  # type: ignore[arg-type]
        lines = node.author("widget-0", "Revenue", _result())
        assert json.loads(lines[0])["path"] == "/elements/widget-0-chart"
        assert json.loads(lines[0])["value"]["props"]["data"] == {"$state": "/widget-0/rows"}
        assert json.loads(lines[1])["value"] == "widget-0-chart"

    def test_falls_back_to_namespaced_data_table(self) -> None:
        node = GenerateWidgetView(FakeViewModel("sorry"), "prompt", PlainTextExtractor())  # type: ignore[arg-type]
        lines = [json.loads(line) for line in node.author("widget-3", "T", _result())]
        table = next(p for p in lines if p["path"].startswith("/elements/widget-3-"))
        assert table["value"]["type"] == "DataTable"
        assert table["value"]["props"]["data"] == {"$state": "/widget-3"}

    def test_prompt_has_title_and_schema_not_values(self) -> None:
        model = FakeViewModel('{"op":"add","path":"/elements/x","value":{"type":"KpiStat"}}')
        GenerateWidgetView(model, "prompt", PlainTextExtractor()).author(
            "widget-0", "Revenue title", _result()
        )  # type: ignore[arg-type]
        human = str(model.received[-1].content)
        assert "Revenue title" in human and "month" in human and "number" in human
        assert "Jan" not in human and "100" not in human
