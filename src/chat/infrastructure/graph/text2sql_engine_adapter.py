"""Adapter exposing the compiled text2sql graph behind the Text2SqlPort."""

from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import cast
from uuid import uuid4

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.text2sql_result import Text2SqlResult
from chat.infrastructure.graph.types import TypedChatGraph
from chat.infrastructure.graph.view.render_tree_builder import narrative_tree
from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)

_TIMEOUT_RESPONSE = (
    "This query is taking longer than expected. Please try again or rephrase your question."
)


class Text2SqlEngineAdapter:
    """Wraps the compiled graph and maps its final state to a Text2SqlResult.

    Owns the per-question timeout (graceful fallback rather than a hung request)
    so that logic lives in one place shared by the CLI and the API.

    Example:
        engine = Text2SqlEngineAdapter(graph, timeout_s=120.0)
        result = engine.answer("How many orders were delivered?")
    """

    def __init__(self, graph: TypedChatGraph, timeout_s: float | None = None) -> None:
        """Wire the compiled graph and an optional per-question timeout in seconds."""
        self._graph = graph
        self._timeout_s = timeout_s

    def answer(self, question: str) -> Text2SqlResult:
        """Answer a question, returning a graceful timeout result if it runs too long."""
        request_id = str(uuid4())
        initial_state = cast(ChatState, {"question": question, "request_id": request_id})
        _logger.info(
            "graph.start",
            extra={"request_id": request_id, "question_length": len(question)},
        )
        t0 = perf_counter()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                self._graph.invoke,  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
                initial_state,
            )
            try:
                raw = future.result(timeout=self._timeout_s)
            except TimeoutError:
                _logger.warning(
                    "graph.timeout",
                    extra={"request_id": request_id, "timeout_s": self._timeout_s},
                )
                return _timeout_result()
        duration_ms = round((perf_counter() - t0) * 1000)
        _logger.info("graph.complete", extra={"request_id": request_id, "duration_ms": duration_ms})
        return _to_result(cast(ChatState, raw))


def _to_result(state: ChatState) -> Text2SqlResult:
    """Map a completed ChatState to a Text2SqlResult, defaulting a missing view."""
    data = cast(dict[str, object], state)
    response = state["response"]
    view = data.get("view")
    sql_query = data.get("sql_query")
    return Text2SqlResult(
        response=response,
        sql_query=sql_query if isinstance(sql_query, str) else "",
        view=view if isinstance(view, RenderTree) else narrative_tree(response),
    )


def _timeout_result() -> Text2SqlResult:
    """Build the graceful result returned when a query exceeds the timeout."""
    return Text2SqlResult(
        response=_TIMEOUT_RESPONSE, sql_query="", view=narrative_tree(_TIMEOUT_RESPONSE)
    )
