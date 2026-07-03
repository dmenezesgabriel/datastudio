"""Tests for converting stored conversation turns into LangChain messages."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from chat.domain.value_objects.message import Message
from chat.infrastructure.graph.history_messages import to_chat_history


def _user(content: str) -> Message:
    return Message(role="user", content=content, view=None)


def _assistant(content: str) -> Message:
    return Message(role="assistant", content=content, view=None)


class TestToChatHistory:
    def test_maps_roles_to_message_types_in_order(self) -> None:
        # arrange — a two-turn exchange
        history = [_user("How many orders?"), _assistant("There are 42.")]
        # act
        messages = to_chat_history(history)
        # assert — user -> Human, assistant -> AI, order preserved, content carried
        assert [type(m).__name__ for m in messages] == ["HumanMessage", "AIMessage"]
        assert isinstance(messages[0], HumanMessage) and messages[0].content == "How many orders?"
        assert isinstance(messages[1], AIMessage) and messages[1].content == "There are 42."

    def test_empty_history_yields_no_messages(self) -> None:
        assert to_chat_history([]) == []

    def test_unknown_role_raises_with_offending_value(self) -> None:
        bad = Message(role="system", content="x", view=None)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="system"):
            to_chat_history([bad])
