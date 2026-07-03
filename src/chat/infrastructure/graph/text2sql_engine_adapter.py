"""Adapter exposing the compiled text2sql graph behind the Text2SqlPort."""

import asyncio
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import cast
from uuid import uuid4

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.message import Message
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    ProgressUpdate,
    SqlReady,
    TypedChatStream,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.domain.value_objects.text2sql_result import Text2SqlResult
from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.graph.history_messages import to_chat_history
from chat.infrastructure.graph.types import TypedChatGraph
from chat.infrastructure.graph.view.render_tree_builder import compile_view_tree, narrative_tree
from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)

_TIMEOUT_RESPONSE = (
    "This query is taking longer than expected. Please try again or rephrase your question."
)

# Nodes whose completion is shown as progress while the dashboard is being built.
# build_widget (data + view), compose_narrative (summary) are handled explicitly.
_PROGRESS_NODES = frozenset({"list_tables", "select_tables", "get_schema", "plan_widgets"})


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
        """Answer a single question with no conversation memory (stateless CLI path).

        The CLI is a memory-less entry point, so history is always empty here — the
        HTTP path (:meth:`stream`) is the one that carries short-term memory.
        """
        request_id = str(uuid4())
        initial_state = cast(
            ChatState, {"question": question, "request_id": request_id, "history": []}
        )
        _logger.info(
            "graph.start",
            extra={
                "request_id": request_id,
                "question_length": len(question),
                "history_message_count": 0,
            },
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

    async def stream(self, question: str, history: Sequence[Message]) -> TypedChatStream:
        """Stream the answer as it is produced: progress, then narrative, then view.

        ``history`` is the prior-turn conversation window (short-term memory); it is
        converted to LangChain messages and seeded into the graph state so the LLM
        nodes can resolve follow-ups. Uses LangGraph's native
        ``astream(stream_mode="updates")`` with an ``asyncio.timeout`` budget (no
        thread pool), so each node's output reaches the caller the moment it
        completes. On timeout it yields the same graceful fallback as ``answer``
        instead of leaving the stream hanging.

        Example:
            async for event in engine.stream("How many orders?", []):
                ...
        """
        request_id = str(uuid4())
        initial_state = cast(
            ChatState,
            {
                "question": question,
                "request_id": request_id,
                "history": to_chat_history(history),
            },
        )
        _logger.info(
            "graph.stream.start",
            extra={
                "request_id": request_id,
                "question_length": len(question),
                "history_message_count": len(history),
            },
        )
        try:
            async with asyncio.timeout(self._timeout_s):
                async for chunk in self._graph.astream(  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
                    initial_state, stream_mode="updates"
                ):
                    for node_name, update in cast(
                        Mapping[str, Mapping[str, object]], chunk
                    ).items():
                        for event in _events_for(node_name, update):
                            yield event
        except TimeoutError:
            _logger.warning(
                "graph.stream.timeout",
                extra={"request_id": request_id, "timeout_s": self._timeout_s},
            )
            yield NarrativeReady(text=_TIMEOUT_RESPONSE)
            return
        _logger.info("graph.stream.complete", extra={"request_id": request_id})


def _events_for(node_name: str, update: Mapping[str, object]) -> list[ChatStreamEvent]:
    """Map one node update to zero or more stream events (silent nodes yield none)."""
    if node_name in _PROGRESS_NODES:
        return [ProgressUpdate(stage=node_name)]
    if node_name == "build_widget":
        return _widget_events(update)
    if node_name == "compose_narrative":
        response = update.get("response")
        return [NarrativeReady(text=response)] if isinstance(response, str) else []
    return []


def _widget_events(update: Mapping[str, object]) -> list[ChatStreamEvent]:
    """Map one finished build_widget worker to its data patch, view patches, and SQL.

    Data first (so ``$state`` exists when the view binds), then the namespaced view
    lines, then the SQL disclosure. A failed widget yields only its note view lines.
    """
    results = [r for r in _as_list(update.get("widget_results")) if isinstance(r, WidgetResult)]
    lines = [ln for ln in _as_list(update.get("widget_views")) if isinstance(ln, str)]
    events: list[ChatStreamEvent] = [
        WidgetDataReady(widget_id=r.widget_id, result=r.result) for r in results
    ]
    events += [ViewPatchLine(line=line) for line in lines]
    events += [SqlReady(widget_id=r.widget_id, sql_query=r.sql) for r in results if r.sql]
    return events


def _as_list(value: object) -> list[object]:
    """Return value as a list of objects, or empty when it is not a list."""
    return cast(list[object], value) if isinstance(value, list) else []


def _to_result(state: ChatState) -> Text2SqlResult:
    """Map a completed ChatState to a Text2SqlResult for the sync (CLI) path.

    Compiles the aggregated widget view patches into a render tree (used by the CLI,
    which only prints ``response``); falls back to narrative-only when no widget ran.
    """
    data = cast(dict[str, object], state)
    response = state["response"]
    results = [r for r in _as_list(data.get("widget_results")) if isinstance(r, WidgetResult)]
    sql = "; ".join(r.sql for r in results)
    lines = [ln for ln in _as_list(data.get("widget_views")) if isinstance(ln, str)]
    view = compile_view_tree(response, lines, "") if lines else narrative_tree(response)
    return Text2SqlResult(response=response, sql_query=sql, view=view)


def _timeout_result() -> Text2SqlResult:
    """Build the graceful result returned when a query exceeds the timeout."""
    return Text2SqlResult(
        response=_TIMEOUT_RESPONSE, sql_query="", view=narrative_tree(_TIMEOUT_RESPONSE)
    )
