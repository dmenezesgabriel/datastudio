"""FastAPI router exposing the chat endpoint over the SendMessage use case."""

from time import perf_counter

from fastapi import APIRouter

from chat.application.use_cases.send_message import SendMessage
from chat.infrastructure.api.chat_request import ChatRequest
from chat.infrastructure.api.chat_response import ChatResponse
from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)


class ChatRouter:
    """Builds an APIRouter that drives the SendMessage use case.

    Thin driving adapter: it parses the request, delegates to the use case, and
    serializes the result. No graph or persistence detail leaks in here.

    Example:
        router = ChatRouter(send_message).router
        app.include_router(router)
    """

    def __init__(self, send_message: SendMessage) -> None:
        """Wire the use case and register routes on a fresh APIRouter."""
        self._send_message = send_message
        self.router = APIRouter()
        self.router.add_api_route("/api/chat", self._handle_chat, methods=["POST"])

    def _handle_chat(self, request: ChatRequest) -> ChatResponse:
        """Answer one question within its conversation."""
        cid = request.conversation_id
        _logger.info(
            "chat.request.received",
            extra={"conversation_id": cid, "question_length": len(request.question)},
        )
        t0 = perf_counter()
        try:
            result = self._send_message.execute(cid, request.question)
        except Exception:
            _logger.error("chat.request.error", extra={"conversation_id": cid}, exc_info=True)
            raise
        duration_ms = round((perf_counter() - t0) * 1000)
        _logger.info(
            "chat.request.completed",
            extra={
                "conversation_id": cid,
                "duration_ms": duration_ms,
                "has_sql": bool(result.sql_query),
            },
        )
        return ChatResponse(
            conversation_id=cid,
            response=result.response,
            sql_query=result.sql_query,
            view=result.view,
        )
