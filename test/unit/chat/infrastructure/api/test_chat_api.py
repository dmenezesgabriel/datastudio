"""Tests for the chat component's HTTP assembly seam (build_chat_routers)."""

from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chat.application.use_cases.stream_message import StreamMessage
from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.stream_event import ChatStreamEvent
from chat.domain.value_objects.text2sql_result import Text2SqlResult
from chat.infrastructure.api.chat_api import build_chat_routers
from chat.infrastructure.persistence.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from test.unit.chat.infrastructure.api.fakes import FakeCurrentUser


class FakeStreamMessage:
    """Stands in for the StreamMessage use case; never runs the graph."""

    async def execute(
        self, owner_id: str, conversation_id: str, question: str
    ) -> AsyncIterator[ChatStreamEvent]:
        # The router-assembly tests never drive the write path, so this yields nothing.
        return
        yield  # pragma: no cover - marks this an async generator


def _narrative_result(text: str) -> Text2SqlResult:
    view = RenderTree(
        root="root",
        elements={
            "root": RenderElement(type="Stack", props={}, children=["narrative"]),
            "narrative": RenderElement(type="Markdown", props={"text": text}, children=[]),
        },
    )
    return Text2SqlResult(narrative=text, view=view)


def _repo_with_one_turn() -> InMemoryConversationRepository:
    repo = InMemoryConversationRepository()
    conversation = Conversation.new("c-1", "u-1")
    conversation.append_user_message("How many orders?")
    conversation.append_assistant_message(_narrative_result("There are 42 orders."))
    repo.save(conversation)
    return repo


def _client(repo: InMemoryConversationRepository) -> TestClient:
    app = FastAPI()
    stream_message = cast(StreamMessage, FakeStreamMessage())
    for router in build_chat_routers(stream_message, repo, FakeCurrentUser("u-1")):
        app.include_router(router)
    return TestClient(app)


class TestBuildChatRouters:
    def test_exposes_chat_and_conversation_routes(self) -> None:
        # arrange
        app = FastAPI()
        stream_message = cast(StreamMessage, FakeStreamMessage())
        # act
        for router in build_chat_routers(
            stream_message, InMemoryConversationRepository(), FakeCurrentUser("u-1")
        ):
            app.include_router(router)
        paths = set(app.openapi()["paths"])
        # assert
        assert {
            "/api/chat",
            "/api/conversations",
            "/api/conversations/{conversation_id}",
        } <= paths

    def test_conversations_route_reads_the_injected_repository(self) -> None:
        # arrange — the read router must serve from the very repo it was handed
        client = _client(_repo_with_one_turn())
        # act
        body = client.get("/api/conversations").json()
        # assert
        assert body["conversations"][0]["conversation_id"] == "c-1"
        assert body["conversations"][0]["title"] == "How many orders?"
