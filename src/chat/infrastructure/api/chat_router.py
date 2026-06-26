"""FastAPI router exposing the chat endpoint over the SendMessage use case."""

from fastapi import APIRouter

from chat.application.use_cases.send_message import SendMessage
from chat.infrastructure.api.chat_request import ChatRequest
from chat.infrastructure.api.chat_response import ChatResponse


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
        result = self._send_message.execute(request.conversation_id, request.question)
        return ChatResponse(
            conversation_id=request.conversation_id,
            response=result.response,
            sql_query=result.sql_query,
            view=result.view,
        )
