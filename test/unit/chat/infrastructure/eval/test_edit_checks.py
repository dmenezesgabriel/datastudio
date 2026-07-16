"""Unit tests for the conversational-edit checks over a merged dashboard spec."""

from typing import cast

from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.infrastructure.eval.edit_checks import (
    EditModeCheck,
    ElementRemovedCheck,
    WidgetKindCheck,
    WidgetsPreservedCheck,
)
from chat.infrastructure.graph.chat_state import ChatState


def _tree(*widgets: tuple[str, str, str | None]) -> RenderTree:
    """Build a dashboard tree from (widget_id, leaf_type, chart_kind) triples.

    Each widget owns a ``<id>-frame`` frame wrapping one leaf element, mirroring the real
    F-layout spec so the edit checks resolve leaves the same way production does.
    """
    elements: dict[str, RenderElement] = {}
    children: list[str] = []
    for widget_id, leaf_type, kind in widgets:
        leaf_id = f"{widget_id}-leaf"
        props: dict[str, object] = {"kind": kind} if kind is not None else {}
        elements[leaf_id] = RenderElement(type=leaf_type, props=props, children=[])
        elements[f"{widget_id}-frame"] = RenderElement(
            type="WidgetFrame", props={}, children=[leaf_id]
        )
        children.append(f"{widget_id}-frame")
    elements["root"] = RenderElement(type="Stack", props={}, children=children)
    return RenderTree(root="root", elements=elements)


def _state(spec: RenderTree | None = None, edit_mode: str | None = None) -> ChatState:
    """A ChatState carrying the runner-stashed edited spec and classifier mode."""
    return cast(ChatState, {"edited_spec": spec, "edit_mode": edit_mode})


class TestEditModeCheck:
    """edit_mode passes only when the classifier chose the expected route."""

    def test_passes_when_mode_matches(self) -> None:
        # arrange / act
        result = EditModeCheck("restyle").evaluate(_state(edit_mode="restyle"))
        # assert
        assert result["passed"] is True

    def test_fails_when_mode_differs(self) -> None:
        # arrange / act
        result = EditModeCheck("reanalyze").evaluate(_state(edit_mode="restyle"))
        # assert
        assert result["passed"] is False
        assert "restyle" in result["reasoning"]


class TestWidgetKindCheck:
    """widget_kind grades a widget's leaf type and chart kind on the edited spec."""

    def test_passes_when_type_and_kind_match(self) -> None:
        # arrange — widget-0 became a bar chart
        spec = _tree(("widget-0", "ChartJs", "bar"))
        # act
        result = WidgetKindCheck("widget-0", "ChartJs", "bar").evaluate(_state(spec))
        # assert
        assert result["passed"] is True

    def test_fails_when_chart_kind_differs(self) -> None:
        # arrange — still a chart, but the wrong kind
        spec = _tree(("widget-0", "ChartJs", "line"))
        # act
        result = WidgetKindCheck("widget-0", "ChartJs", "bar").evaluate(_state(spec))
        # assert
        assert result["passed"] is False

    def test_matches_type_when_no_kind_required(self) -> None:
        # arrange — a KpiStat has no chart kind
        spec = _tree(("widget-0", "KpiStat", None))
        # act
        result = WidgetKindCheck("widget-0", "KpiStat").evaluate(_state(spec))
        # assert
        assert result["passed"] is True

    def test_fails_when_widget_absent(self) -> None:
        # arrange — the target id is not on the dashboard
        spec = _tree(("widget-0", "ChartJs", "bar"))
        # act
        result = WidgetKindCheck("widget-9", "ChartJs", "bar").evaluate(_state(spec))
        # assert
        assert result["passed"] is False

    def test_fails_when_no_edited_spec(self) -> None:
        # arrange — check attached to a turn with no stashed spec
        result = WidgetKindCheck("widget-0", "ChartJs").evaluate(_state(None))
        # assert
        assert result["passed"] is False
        assert "no edited spec" in result["reasoning"]


class TestWidgetsPreservedCheck:
    """widgets_preserved fails when an untouched widget was dropped by the edit."""

    def test_passes_when_all_present(self) -> None:
        # arrange — both widgets survive
        spec = _tree(("widget-0", "KpiStat", None), ("widget-1", "KpiStat", None))
        # act
        result = WidgetsPreservedCheck(["widget-0", "widget-1"]).evaluate(_state(spec))
        # assert
        assert result["passed"] is True

    def test_fails_when_a_widget_is_missing(self) -> None:
        # arrange — widget-1 was collaterally dropped
        spec = _tree(("widget-0", "KpiStat", None))
        # act
        result = WidgetsPreservedCheck(["widget-0", "widget-1"]).evaluate(_state(spec))
        # assert
        assert result["passed"] is False
        assert "widget-1" in result["reasoning"]


class TestElementRemovedCheck:
    """element_removed passes only when the named element is gone."""

    def test_passes_when_element_absent(self) -> None:
        # arrange — widget-1 frame was removed
        spec = _tree(("widget-0", "KpiStat", None))
        # act
        result = ElementRemovedCheck("widget-1-frame").evaluate(_state(spec))
        # assert
        assert result["passed"] is True

    def test_fails_when_element_still_present(self) -> None:
        # arrange — the frame is still there
        spec = _tree(("widget-0", "KpiStat", None))
        # act
        result = ElementRemovedCheck("widget-0-frame").evaluate(_state(spec))
        # assert
        assert result["passed"] is False
