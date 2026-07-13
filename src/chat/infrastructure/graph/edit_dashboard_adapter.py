"""Adapter exposing the compiled edit graph behind the EditDashboardPort."""

import asyncio
from collections.abc import Mapping
from typing import cast
from uuid import uuid4

from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    ProgressStep,
    TypedChatStream,
)
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.types import TypedChatGraph
from chat.infrastructure.graph.widget_stream_events import widget_events
from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)

_TIMEOUT_NARRATIVE = "This edit is taking longer than expected. Please try again."


class EditDashboardAdapter:
    """Wraps the compiled edit graph and streams its patch events for one instruction.

    Owns the per-edit timeout (graceful fallback rather than a hung request), mirroring
    ``Text2SqlEngineAdapter`` on the build side.

    Example:
        engine = EditDashboardAdapter(graph, timeout_s=120.0)
        async for event in engine.edit(spec, "reorder the widgets"):
            ...
    """

    def __init__(self, graph: TypedChatGraph, timeout_s: float | None = None) -> None:
        """Wire the compiled edit graph and an optional per-edit timeout in seconds."""
        self._graph = graph
        self._timeout_s = timeout_s

    async def edit(self, spec: RenderTree, instruction: str) -> TypedChatStream:
        """Stream the patch events applying ``instruction`` to ``spec``.

        The current spec seeds the graph as ``prior_spec`` (the whole edit state), so no
        conversation memory is needed. On timeout it yields the same graceful fallback as
        the build path instead of leaving the stream hanging.
        """
        request_id = str(uuid4())
        initial_state = cast(
            ChatState,
            {
                "instruction": instruction,
                "prior_spec": spec,
                "question": instruction,
                "history": [],
                "request_id": request_id,
            },
        )
        _logger.info("edit.stream.start", extra={"request_id": request_id})
        try:
            async with asyncio.timeout(self._timeout_s):
                async for mode, chunk in self._graph.astream(  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
                    initial_state, stream_mode=["updates", "custom"]
                ):
                    for event in _edit_events_for_chunk(cast(str, mode), chunk):
                        yield event
        except TimeoutError:
            _logger.warning(
                "edit.stream.timeout",
                extra={"request_id": request_id, "timeout_s": self._timeout_s},
            )
            yield NarrativeReady(text=_TIMEOUT_NARRATIVE)
            return
        _logger.info("edit.stream.complete", extra={"request_id": request_id})


def _edit_events_for_chunk(mode: str, chunk: object) -> list[ChatStreamEvent]:
    """Map one astream item to stream events by its mode (``custom`` vs ``updates``)."""
    if mode == "custom":
        return [chunk] if isinstance(chunk, ProgressStep) else []
    events: list[ChatStreamEvent] = []
    for node_name, update in cast(Mapping[str, Mapping[str, object]], chunk).items():
        events += _edit_events_for(node_name, update)
    return events


def _edit_events_for(node_name: str, update: Mapping[str, object]) -> list[ChatStreamEvent]:
    """Map one edit-node update to patch events; both patch-emitting nodes share the mapping.

    ``author_edit_patches`` (restyle) and ``build_widget`` (reanalyze) both write the
    ``widget_patch_lines``/``widget_results`` channels, so ``widget_events`` surfaces each
    as view patches (plus data + SQL when a widget was rebuilt). Other nodes are silent.
    """
    if node_name in ("author_edit_patches", "build_widget"):
        return widget_events(update)
    return []
