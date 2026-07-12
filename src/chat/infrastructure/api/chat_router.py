"""FastAPI router streaming the chat answer as a json-render SpecStream."""

from collections.abc import AsyncIterator
from time import perf_counter
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from chat.application.use_cases.stream_message import StreamMessage
from chat.domain.value_objects.stream_event import NarrativeReady
from chat.infrastructure.api.chat_request import StreamChatRequest
from chat.infrastructure.api.spec_stream import SpecStreamSerializer
from shared.infrastructure.api.current_user import ResolveOwnerId
from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)

# Headers that keep the NDJSON flowing line-by-line instead of being buffered by
# the dev server / reverse proxies — without them the "stream" arrives as one blob.
_STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
_STREAM_ERROR_MESSAGE = "Something went wrong while answering. Please try again."


class ChatRouter:
    """Builds an APIRouter that streams the StreamMessage use case as SpecStream.

    Thin driving adapter: it parses the request, drives the use case, and
    serializes each event into json-render patch lines. No graph or persistence
    detail leaks in here.

    Example:
        router = ChatRouter(stream_message).router
        app.include_router(router)
    """

    def __init__(self, stream_message: StreamMessage, resolve_current_user: ResolveOwnerId) -> None:
        """Wire the use case and the current-user dependency, then register the route."""
        self._stream_message = stream_message
        self.router = APIRouter()
        self._add_routes(resolve_current_user)

    def _add_routes(self, resolve_current_user: ResolveOwnerId) -> None:
        """Bind the route via a closure so the dependency is a valid ``Depends`` default."""

        async def handle_chat(
            request: StreamChatRequest,
            user_id: Annotated[str, Depends(resolve_current_user)],
        ) -> StreamingResponse:
            return await self._handle_chat(user_id, request)

        self.router.add_api_route("/api/chat", handle_chat, methods=["POST"])

    async def _handle_chat(self, user_id: str, request: StreamChatRequest) -> StreamingResponse:
        """Stream one answer as newline-delimited json-render patches."""
        cid = str(request.context.get("conversation_id") or uuid4())
        _logger.info(
            "chat.request.received",
            extra={
                "owner_id": user_id,
                "conversation_id": cid,
                "question_length": len(request.prompt),
            },
        )
        generator = self._stream_patches(user_id, cid, request.prompt)
        return StreamingResponse(
            generator, media_type="application/x-ndjson", headers=_STREAM_HEADERS
        )

    async def _stream_patches(
        self, owner_id: str, conversation_id: str, prompt: str
    ) -> AsyncIterator[str]:
        """Serialize use-case events to NDJSON; on failure, stream a graceful message."""
        serializer = SpecStreamSerializer()
        t0 = perf_counter()
        try:
            async for event in self._stream_message.execute(owner_id, conversation_id, prompt):
                for line in serializer.lines_for(event):
                    yield line + "\n"
        except Exception:
            _logger.error(
                "chat.request.error", extra={"conversation_id": conversation_id}, exc_info=True
            )
            for line in serializer.lines_for(NarrativeReady(text=_STREAM_ERROR_MESSAGE)):
                yield line + "\n"
            return
        duration_ms = round((perf_counter() - t0) * 1000)
        _logger.info(
            "chat.request.completed",
            extra={"conversation_id": conversation_id, "duration_ms": duration_ms},
        )
