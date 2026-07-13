from typing import cast

from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.widget import WidgetSpec
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes.classify_edit import ClassifyEdit
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)


def _dashboard() -> RenderTree:
    return RenderTree(
        root="root",
        elements={
            "root": RenderElement(type="Stack", props={}, children=["grid"]),
            "grid": RenderElement(type="Grid", props={}, children=["widget-0-frame"]),
            "widget-0-frame": RenderElement(
                type="WidgetFrame", props={"sql": "SELECT 1"}, children=["widget-0-chart"]
            ),
            "widget-0-chart": RenderElement(
                type="ChartJs", props={"kind": "bar", "title": "Revenue"}, children=[]
            ),
        },
    )


def _state(instruction: str) -> ChatState:
    return ChatState(  # type: ignore[call-arg]
        instruction=instruction, prior_spec=_dashboard(), question="", history=[]
    )


class TestClassifyEditRestyle:
    def test_routes_a_restyle_without_seeding_a_widget(self) -> None:
        model = FakeStructuredChatModel(mode="restyle")
        result = ClassifyEdit(model)(_state("make it a line chart"))
        assert result == {"edit_mode": "restyle"}


class TestClassifyEditReanalyze:
    def test_reuses_an_existing_target_widget_id(self) -> None:
        model = FakeStructuredChatModel(
            mode="reanalyze",
            target_widget_id="widget-0",
            title="Revenue by month",
            sub_question="revenue by month",
            role="analysis",
        )
        result = ClassifyEdit(model)(_state("break it down by month"))
        assert result["edit_mode"] == "reanalyze"
        assert result["target_widget_id"] == "widget-0"
        assert result["question"] == "revenue by month"
        widget = cast(WidgetSpec, result["widget"])
        assert widget.id == "widget-0"

    def test_mints_a_fresh_id_when_adding_a_new_widget(self) -> None:
        # An empty target means "add a new widget"; the id must not collide with widget-0.
        model = FakeStructuredChatModel(
            mode="reanalyze",
            target_widget_id="",
            title="Orders",
            sub_question="orders by region",
            role="analysis",
        )
        result = ClassifyEdit(model)(_state("add orders by region"))
        assert result["target_widget_id"] == "widget-1"

    def test_falls_back_to_the_instruction_when_no_sub_question(self) -> None:
        model = FakeStructuredChatModel(
            mode="reanalyze",
            target_widget_id="widget-0",
            title="",
            sub_question="",
            role="analysis",
        )
        result = ClassifyEdit(model)(_state("show me the trend"))
        assert result["question"] == "show me the trend"
