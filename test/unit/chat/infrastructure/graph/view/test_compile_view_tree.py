"""Tests for compiling LLM-authored SpecStream lines into a RenderTree (sync path)."""

import json

from chat.infrastructure.graph.view.render_tree_builder import compile_view_tree


def _add_element(element_id: str, element: dict[str, object]) -> str:
    return json.dumps({"op": "add", "path": f"/elements/{element_id}", "value": element})


# Widget lines are already region-namespaced upstream (see namespace_widget_patches),
# so a chart/table targets the grid region rather than the root directly.
def _append_to_grid(element_id: str) -> str:
    return json.dumps({"op": "add", "path": "/elements/grid/children/-", "value": element_id})


class TestCompileViewTree:
    def test_base_is_the_f_layout_skeleton(self) -> None:
        tree = compile_view_tree("42 orders.", [], {})
        assert tree.root == "root"
        assert tree.elements["narrative"].props["text"] == "42 orders."
        # narrative leads, then the (empty) KPI band and grid regions
        assert tree.elements["root"].children == ["narrative", "kpi-row", "grid"]
        assert tree.elements["kpi-row"].type == "KpiRow"
        assert tree.elements["grid"].type == "Grid"

    def test_applies_llm_view_patches_into_the_grid(self) -> None:
        # Arrange
        chart = {"type": "ChartJs", "props": {"data": {"$state": "/result/rows"}}, "children": []}
        lines = [_add_element("chart-1", chart), _append_to_grid("chart-1")]
        # Act
        tree = compile_view_tree("answer", lines, {})
        # Assert
        assert tree.elements["chart-1"].type == "ChartJs"
        assert tree.elements["chart-1"].props["data"] == {"$state": "/result/rows"}
        assert tree.elements["grid"].children == ["chart-1"]

    def test_sets_sql_on_the_widget_frame(self) -> None:
        # Arrange — a frame element as namespace_widget_patches would emit, placed in the grid
        frame = {"type": "WidgetFrame", "props": {"sql": ""}, "children": ["widget-0-chart"]}
        lines = [_add_element("widget-0-frame", frame), _append_to_grid("widget-0-frame")]
        # Act
        tree = compile_view_tree("answer", lines, {"widget-0": "SELECT 1"})
        # Assert — the SQL lands on the frame's prop; no separate disclosure element
        assert tree.elements["widget-0-frame"].props["sql"] == "SELECT 1"
        assert "sql" not in tree.elements

    def test_ignores_malformed_and_missing_target_lines(self) -> None:
        # Arrange — junk, plus a prop-replace on an element that was never added
        lines = [
            "not json",
            json.dumps({"op": "replace", "path": "/elements/ghost/props/x", "value": 1}),
        ]
        # Act
        tree = compile_view_tree("answer", lines, {})
        # Assert — base survives, no crash
        assert tree.elements["root"].children == ["narrative", "kpi-row", "grid"]
        assert "ghost" not in tree.elements
