"""Tests for compiling LLM-authored SpecStream lines into a RenderTree (sync path)."""

import json

from chat.infrastructure.graph.view.render_tree_builder import compile_view_tree


def _add_element(element_id: str, element: dict[str, object]) -> str:
    return json.dumps({"op": "add", "path": f"/elements/{element_id}", "value": element})


def _append_child(element_id: str) -> str:
    return json.dumps({"op": "add", "path": "/elements/root/children/-", "value": element_id})


class TestCompileViewTree:
    def test_base_has_root_and_narrative(self) -> None:
        tree = compile_view_tree("42 orders.", [], "")
        assert tree.root == "root"
        assert tree.elements["narrative"].props["text"] == "42 orders."
        assert tree.elements["root"].children == ["narrative"]

    def test_applies_llm_view_patches(self) -> None:
        # Arrange
        chart = {"type": "ChartJs", "props": {"data": {"$state": "/result/rows"}}, "children": []}
        lines = [_add_element("chart-1", chart), _append_child("chart-1")]
        # Act
        tree = compile_view_tree("answer", lines, "")
        # Assert
        assert tree.elements["chart-1"].type == "ChartJs"
        assert tree.elements["chart-1"].props["data"] == {"$state": "/result/rows"}
        assert tree.elements["root"].children == ["narrative", "chart-1"]

    def test_appends_sql_disclosure_last(self) -> None:
        tree = compile_view_tree("answer", [], "SELECT 1")
        assert tree.elements["root"].children[-1] == "sql"
        assert "```sql" in tree.elements["sql"].props["text"]
        assert "SELECT 1" in tree.elements["sql"].props["text"]

    def test_ignores_malformed_and_missing_target_lines(self) -> None:
        # Arrange — junk, plus a prop-replace on an element that was never added
        lines = [
            "not json",
            json.dumps({"op": "replace", "path": "/elements/ghost/props/x", "value": 1}),
        ]
        # Act
        tree = compile_view_tree("answer", lines, "")
        # Assert — base survives, no crash
        assert tree.elements["root"].children == ["narrative"]
        assert "ghost" not in tree.elements
