"""Tests for the plan_widgets orchestrator node."""

from types import SimpleNamespace
from typing import Any, cast

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.graph.nodes.plan_widgets import PlanWidgets


class FakePlanModel:
    """Returns a canned plan and records the messages it answered."""

    def __init__(self, widgets: list[SimpleNamespace]) -> None:
        self._plan = SimpleNamespace(widgets=widgets)
        self.received: list[Any] = []

    def with_structured_output(self, schema: Any, **kwargs: Any) -> "FakePlanModel":
        return self

    def invoke(self, messages: list[Any]) -> SimpleNamespace:
        self.received = messages
        return self._plan


def _intent(title: str, sub_question: str) -> SimpleNamespace:
    return SimpleNamespace(title=title, sub_question=sub_question)


def _node(widgets: list[SimpleNamespace], **kwargs: Any) -> PlanWidgets:
    return PlanWidgets(cast(Any, FakePlanModel(widgets)), **kwargs)


def _state(question: str = "q", schema: str = "-- orders") -> ChatState:
    return cast(ChatState, {"question": question, "schema": schema})


class TestPlanWidgets:
    def test_assigns_sequential_ids_to_planned_widgets(self) -> None:
        # Arrange — the model proposes three widgets (ids are NOT trusted from the model)
        node = _node(
            [_intent("KPI", "total"), _intent("Trend", "by month"), _intent("Table", "rows")]
        )
        # Act
        out = node(_state())
        # Assert — ids are assigned deterministically so $state paths never collide
        specs = out["widget_specs"]
        assert [s.id for s in specs] == ["widget-0", "widget-1", "widget-2"]
        assert [s.title for s in specs] == ["KPI", "Trend", "Table"]
        assert specs[1].sub_question == "by month"

    def test_caps_widget_count(self) -> None:
        node = _node([_intent(f"W{i}", f"q{i}") for i in range(8)], max_widgets=3)
        assert len(node(_state())["widget_specs"]) == 3

    def test_empty_plan_falls_back_to_one_widget_for_the_question(self) -> None:
        node = _node([])
        specs = node(_state(question="How many orders?"))["widget_specs"]
        assert len(specs) == 1
        assert specs[0].id == "widget-0"
        assert specs[0].sub_question == "How many orders?"

    def test_prompt_includes_question_and_schema(self) -> None:
        model = FakePlanModel([_intent("KPI", "total")])
        PlanWidgets(cast(Any, model))(_state(question="Revenue?", schema="-- sales\namount INT"))
        human = str(model.received[-1].content)
        assert "Revenue?" in human and "-- sales" in human
