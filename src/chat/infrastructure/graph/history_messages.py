"""Convert stored conversation turns into LangChain messages for the graph.

This is the single boundary where domain ``Message`` turns become the
``list[BaseMessage]`` the LLM nodes splice into their prompts, so the application
layer stays LangChain-free and the nodes never touch the domain ``Message`` type.
"""

from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from chat.domain.value_objects.message import Message


def to_chat_history(messages: Sequence[Message]) -> list[BaseMessage]:
    """Map domain turns to LangChain messages (content only; the ``view`` is dropped).

    User turns become ``HumanMessage`` and assistant turns ``AIMessage`` so the model
    reads the exchange as a dialog. The renderable ``view`` is presentation-only and
    carries no extra signal for follow-up reasoning, so it is intentionally omitted.

    Example:
        to_chat_history([Message("user", "Sales?", None)]) == [HumanMessage("Sales?")]
    """
    return [_to_message(message) for message in messages]


def _to_message(message: Message) -> BaseMessage:
    """Map one domain turn to its LangChain counterpart by role."""
    if message.role == "user":
        return HumanMessage(content=message.content)
    if message.role == "assistant":
        return AIMessage(content=message.content)
    raise ValueError(f"unknown message role {message.role!r}; expected 'user' or 'assistant'")
