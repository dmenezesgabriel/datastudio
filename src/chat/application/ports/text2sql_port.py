"""Port interface for answering questions through the text2sql pipeline."""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from chat.domain.value_objects.message import Message
from chat.domain.value_objects.stream_event import TypedChatStream


@runtime_checkable
class Text2SqlPort(Protocol):
    """Contract for turning a natural-language question into a streamed answer + view.

    Hides the LangGraph pipeline from the application layer so use cases depend on
    this abstraction rather than on graph internals or LangChain. The answer is
    delivered as a stream of events (progress, then narrative, then view) so the
    transport can render it incrementally.

    Example:
        engine: Text2SqlPort = Text2SqlEngineAdapter(graph, timeout_s=120.0)
        async for event in engine.stream("How many events were there?", []):
            ...
    """

    def stream(self, question: str, history: Sequence[Message]) -> TypedChatStream:
        """Stream the answer to a question, given the prior-turn conversation history."""
        ...
