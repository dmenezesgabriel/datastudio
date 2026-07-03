"""FastAPI router exposing the conversation list and a single conversation's transcript.

Read-only sidebar support: lists past threads and returns one thread's turns as
renderable json-render specs, so the client can reopen it and continue. Separate from
``ChatRouter`` (which streams answers) to keep each router single-purpose.
"""

from fastapi import APIRouter, HTTPException

from chat.application.ports.conversation_repository import ConversationRepository
from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.message import Message


class ConversationsRouter:
    """Builds an APIRouter for reading conversations (list + transcript).

    Example:
        router = ConversationsRouter(repository).router
        app.include_router(router)
    """

    def __init__(self, repository: ConversationRepository) -> None:
        """Wire the conversation repository and register the read routes."""
        self._repository = repository
        self.router = APIRouter()
        self.router.add_api_route("/api/conversations", self._list, methods=["GET"])
        self.router.add_api_route(
            "/api/conversations/{conversation_id}", self._get, methods=["GET"]
        )

    def _list(self) -> dict[str, object]:
        """Return sidebar summaries of every stored conversation, most-recent first."""
        summaries = self._repository.list_summaries()
        return {
            "conversations": [
                {
                    "conversation_id": s.conversation_id,
                    "title": s.title,
                    "message_count": s.message_count,
                    "updated_at": s.updated_at,
                }
                for s in summaries
            ]
        }

    def _get(self, conversation_id: str) -> dict[str, object]:
        """Return one conversation's transcript as renderable turns, or 404 if absent."""
        conversation = self._repository.get(conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=404, detail=f"conversation {conversation_id!r} not found"
            )
        return {
            "conversation_id": conversation_id,
            "title": conversation.title(),
            "turns": _turns(conversation),
        }


def _turns(conversation: Conversation) -> list[dict[str, object]]:
    """Pair each user question with the assistant's rendered answer into turns.

    The assistant ``view`` is a persisted json-render tree (narrative summary today); it
    is emitted as a ``{root, elements}`` spec — the exact shape the client's TurnView
    renders — so reopening a thread reuses the live render path.
    """
    turns: list[dict[str, object]] = []
    pending: str | None = None
    for message in conversation.messages:
        if message.role == "user":
            pending = message.content
        elif pending is not None:
            turns.append({"prompt": pending, "spec": _spec_for(message)})
            pending = None
    return turns


def _spec_for(assistant: Message) -> dict[str, object]:
    """The json-render spec for an assistant turn (empty tree when it has no view)."""
    if assistant.view is None:
        return {"root": "root", "elements": {}}
    return assistant.view.model_dump()
