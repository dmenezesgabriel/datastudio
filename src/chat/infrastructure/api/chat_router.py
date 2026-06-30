"""FastAPI router streaming the chat answer as a json-render SpecStream."""

from collections.abc import AsyncIterator
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from chat.application.use_cases.stream_message import StreamMessage
from chat.domain.value_objects.stream_event import NarrativeReady
from chat.infrastructure.api.chat_request import StreamChatRequest
from chat.infrastructure.api.spec_stream import SpecStreamSerializer
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

    def __init__(self, stream_message: StreamMessage) -> None:
        """Wire the use case and register the streaming chat route."""
        self._stream_message = stream_message
        self.router = APIRouter()
        self.router.add_api_route("/api/chat", self._handle_chat, methods=["POST"])

    async def _handle_chat(self, request: StreamChatRequest) -> StreamingResponse:
        """Stream one answer as newline-delimited json-render patches."""
        cid = str(request.context.get("conversation_id") or uuid4())
        _logger.info(
            "chat.request.received",
            extra={"conversation_id": cid, "question_length": len(request.prompt)},
        )
        generator = self._stream_patches(cid, request.prompt)
        return StreamingResponse(
            generator, media_type="application/x-ndjson", headers=_STREAM_HEADERS
        )

    async def _stream_patches(self, conversation_id: str, prompt: str) -> AsyncIterator[str]:
        """Serialize use-case events to NDJSON; on failure, stream a graceful message."""
        serializer = SpecStreamSerializer()
        t0 = perf_counter()
        try:
            async for event in self._stream_message.execute(conversation_id, prompt):
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
