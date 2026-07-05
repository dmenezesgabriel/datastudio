"""Tests for the plan_widgets orchestrator node."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from langchain_core.exceptions import OutputParserException

from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes.plan_widgets import PlanWidgets
from test.unit.chat.infrastructure.graph.nodes.fake_failing_chat_model import (
    FailingStructuredChatModel,
)


class FakePlanModel:
    """Returns a canned plan and records the messages it answered."""

    def __init__(
        self, widgets: list[SimpleNamespace], kind: str = "data", text_answer: str = ""
    ) -> None:
        self._plan = SimpleNamespace(widgets=widgets, kind=kind, text_answer=text_answer)
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


def _state(
    question: str = "q", schema: str = "-- orders", history: list[Any] | None = None
) -> ChatState:
    return cast(ChatState, {"question": question, "schema": schema, "history": history or []})


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

    def test_injects_prior_turns_between_system_and_current_question(self) -> None:
        # arrange — a prior exchange as short-term memory
        from langchain_core.messages import AIMessage, HumanMessage

        model = FakePlanModel([_intent("KPI", "total")])
        history = [HumanMessage(content="prior q"), AIMessage(content="prior a")]
        # act
        PlanWidgets(cast(Any, model))(_state(question="now", history=history))
        # assert — [System, *history, Human(current)] in order
        assert [type(m).__name__ for m in model.received] == [
            "SystemMessage",
            "HumanMessage",
            "AIMessage",
            "HumanMessage",
        ]
        assert model.received[1].content == "prior q"
        assert "now" in str(model.received[-1].content)


class TestPlanWidgetsTextBranch:
    def test_text_kind_returns_trimmed_answer_and_no_widgets(self) -> None:
        # arrange — the planner classifies a meta/greeting question as text
        model = FakePlanModel([], kind="text", text_answer="  I can query your data.  ")
        # act
        out = PlanWidgets(cast(Any, model))(_state(question="what can you do?"))
        # assert — a direct answer, no widget fan-out
        assert out["answer_kind"] == "text"
        assert out["text_answer"] == "I can query your data."
        assert "widget_specs" not in out

    def test_text_kind_without_answer_falls_back_to_data(self) -> None:
        # arrange — kind says text but the model gave no content
        model = FakePlanModel([_intent("KPI", "total")], kind="text", text_answer="   ")
        # act
        out = PlanWidgets(cast(Any, model))(_state(question="revenue?"))
        # assert — degrade to the data path rather than answer with a blank string
        assert out["answer_kind"] == "data"
        assert [s.id for s in out["widget_specs"]] == ["widget-0"]

    def test_data_kind_tags_answer_kind(self) -> None:
        out = _node([_intent("KPI", "total")])(_state())
        assert out["answer_kind"] == "data"

    def test_default_kind_plan_routes_to_widgets(self) -> None:
        # A plan that carries the default kind ("data") and no text_answer must fan out to
        # widgets — the classifier reads plan.kind/plan.text_answer directly (no getattr).
        model = FakePlanModel([_intent("KPI", "total")])  # kind="data", text_answer="" defaults
        out = PlanWidgets(cast(Any, model))(_state(question="revenue?"))
        assert out["answer_kind"] == "data"
        assert [s.id for s in out["widget_specs"]] == ["widget-0"]
        assert "text_answer" not in out


class TestPlanWidgetsResilience:
    def test_malformed_output_falls_back_to_one_widget(self) -> None:
        # arrange — structured plan can't be parsed
        node = PlanWidgets(FailingStructuredChatModel(OutputParserException("bad")))
        # act
        specs = node(_state(question="How many orders?"))["widget_specs"]
        # assert — a single widget mirroring the question, not a crash
        assert len(specs) == 1
        assert specs[0].id == "widget-0"
        assert specs[0].sub_question == "How many orders?"

    def test_transient_error_propagates_to_retry_policy(self) -> None:
        node = PlanWidgets(FailingStructuredChatModel(ConnectionError("blip")))
        with pytest.raises(ConnectionError):
            node(_state())
