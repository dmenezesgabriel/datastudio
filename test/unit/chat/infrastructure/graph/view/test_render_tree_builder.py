"""Tests for the surviving render-tree helpers (narrative + markdown)."""

from chat.infrastructure.graph.view.render_tree_builder import (
    build_markdown_element,
    narrative_tree,
)


class TestBuildMarkdownElement:
    def test_type_is_markdown(self) -> None:
        assert build_markdown_element("hi").type == "Markdown"

    def test_text_prop_matches_input(self) -> None:
        assert build_markdown_element("There are 42 orders.").props == {
            "text": "There are 42 orders."
        }

    def test_no_children(self) -> None:
        assert build_markdown_element("hi").children == []


class TestNarrativeTree:
    def test_root_key_is_root(self) -> None:
        assert narrative_tree("answer").root == "root"

    def test_root_element_is_stack_over_narrative(self) -> None:
        tree = narrative_tree("answer")
        assert tree.elements["root"].type == "Stack"
        assert tree.elements["root"].children == ["narrative"]

    def test_narrative_text_matches_input(self) -> None:
        tree = narrative_tree("There are 42 orders.")
        assert tree.elements["narrative"].props["text"] == "There are 42 orders."
