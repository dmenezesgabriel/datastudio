"""Tests for the read-only conversations API (sidebar list + transcript)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.text2sql_result import Text2SqlResult
from chat.infrastructure.api.conversations_router import ConversationsRouter
from chat.infrastructure.persistence.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from shared.infrastructure.api.error_handlers import register_error_handlers
from test.unit.chat.infrastructure.api.fakes import fake_owner_id

_OWNER = "u-1"


def _narrative_result(text: str) -> Text2SqlResult:
    view = RenderTree(
        root="root",
        elements={
            "root": RenderElement(type="Stack", props={}, children=["narrative"]),
            "narrative": RenderElement(type="Markdown", props={"text": text}, children=[]),
        },
    )
    return Text2SqlResult(narrative=text, view=view)


def _repo_with_one_turn(owner: str = _OWNER) -> InMemoryConversationRepository:
    repo = InMemoryConversationRepository()
    conversation = Conversation.new("c-1", owner)
    conversation.append_user_message("How many orders?")
    conversation.append_assistant_message(_narrative_result("There are 42 orders."))
    repo.save(conversation)
    return repo


def _client(repo: InMemoryConversationRepository, user_id: str = _OWNER) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)  # so ConversationNotFound maps to 404, as in production
    app.include_router(ConversationsRouter(repo, fake_owner_id(user_id)).router)
    return TestClient(app)


class TestListConversations:
    def test_lists_saved_conversations_with_titles(self) -> None:
        # arrange
        client = _client(_repo_with_one_turn())
        # act
        body = client.get("/api/conversations").json()
        # assert
        assert body["conversations"][0]["conversation_id"] == "c-1"
        assert body["conversations"][0]["title"] == "How many orders?"

    def test_empty_when_nothing_saved(self) -> None:
        assert _client(InMemoryConversationRepository()).get("/api/conversations").json() == {
            "conversations": []
        }


class TestGetConversation:
    def test_returns_turns_pairing_question_with_rendered_answer(self) -> None:
        # arrange
        client = _client(_repo_with_one_turn())
        # act
        body = client.get("/api/conversations/c-1").json()
        # assert — one turn: the prompt plus a renderable {root, elements} spec
        assert body["title"] == "How many orders?"
        assert len(body["turns"]) == 1
        turn = body["turns"][0]
        assert turn["prompt"] == "How many orders?"
        assert turn["spec"]["root"] == "root"
        assert turn["spec"]["elements"]["narrative"]["props"]["text"] == "There are 42 orders."

    def test_missing_conversation_returns_404(self) -> None:
        response = _client(InMemoryConversationRepository()).get("/api/conversations/absent")
        assert response.status_code == 404

    def test_another_users_conversation_returns_404(self) -> None:
        # c-1 belongs to _OWNER; bob must not be able to read it (same 404 as absent)
        client = _client(_repo_with_one_turn(), user_id="bob")
        assert client.get("/api/conversations/c-1").status_code == 404


class TestOwnerScoping:
    def test_list_shows_only_the_callers_conversations(self) -> None:
        # the sidebar for bob (who owns nothing here) is empty even though c-1 exists
        client = _client(_repo_with_one_turn(), user_id="bob")
        assert client.get("/api/conversations").json() == {"conversations": []}
