"""Tests for the answer_text node (text-only branch)."""

from typing import Any, cast

from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes.answer_text import AnswerText


def _state(**fields: Any) -> ChatState:
    return cast(ChatState, {"question": "q", "history": [], **fields})


class TestAnswerText:
    def test_promotes_drafted_text_answer_to_response(self) -> None:
        out = AnswerText()(_state(text_answer="I can query your data."))
        assert out == {"response": "I can query your data."}

    def test_trims_surrounding_whitespace(self) -> None:
        out = AnswerText()(_state(text_answer="  hello  "))
        assert out["response"] == "hello"

    def test_blank_answer_falls_back_to_a_prompt_to_rephrase(self) -> None:
        # arrange — planner routed here but left no content (never expected)
        out = AnswerText()(_state(text_answer="   "))
        # assert — a helpful non-empty reply, not a blank string
        assert out["response"] and "rephrase" in out["response"].lower()

    def test_missing_answer_falls_back(self) -> None:
        out = AnswerText()(_state())
        assert out["response"] and "rephrase" in out["response"].lower()
