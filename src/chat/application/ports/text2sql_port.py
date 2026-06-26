"""Port interface for answering questions through the text2sql pipeline."""

from typing import Protocol, runtime_checkable

from chat.domain.value_objects.text2sql_result import Text2SqlResult


@runtime_checkable
class Text2SqlPort(Protocol):
    """Contract for turning a natural-language question into an answer + view.

    Hides the LangGraph pipeline from the application layer so use cases depend
    on this abstraction rather than on graph internals or LangChain.

    Example:
        engine: Text2SqlPort = Text2SqlEngineAdapter(graph, timeout_s=120.0)
        result = engine.answer("How many orders were delivered?")
    """

    def answer(self, question: str) -> Text2SqlResult:
        """Answer a single question, returning the response, SQL, and render tree."""
        ...
