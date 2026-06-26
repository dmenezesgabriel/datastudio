from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chat.application.use_cases.send_message import SendMessage
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.text2sql_result import Text2SqlResult
from chat.infrastructure.api.chat_router import ChatRouter


class FakeSendMessage:
    """Records calls and returns a fixed result instead of running the graph."""

    def __init__(self, result: Text2SqlResult) -> None:
        self._result = result
        self.calls: list[tuple[str, str]] = []

    def execute(self, conversation_id: str, question: str) -> Text2SqlResult:
        self.calls.append((conversation_id, question))
        return self._result


def _client(fake: FakeSendMessage) -> TestClient:
    app = FastAPI()
    app.include_router(ChatRouter(cast(SendMessage, fake)).router)
    return TestClient(app)


def _result() -> Text2SqlResult:
    view = RenderTree(
        root="root",
        elements={"root": RenderElement(type="Stack", props={}, children=[])},
    )
    return Text2SqlResult(response="There are 42 orders.", sql_query="SELECT 1", view=view)


class TestChatRouter:
    def test_post_chat_returns_response_payload(self) -> None:
        # arrange
        fake = FakeSendMessage(_result())
        client = _client(fake)
        # act
        response = client.post(
            "/api/chat", json={"conversation_id": "c-1", "question": "How many orders?"}
        )
        # assert
        assert response.status_code == 200
        body = response.json()
        assert body["conversation_id"] == "c-1"
        assert body["response"] == "There are 42 orders."
        assert body["sql_query"] == "SELECT 1"
        assert body["view"]["root"] == "root"

    def test_post_chat_delegates_to_use_case(self) -> None:
        # arrange
        fake = FakeSendMessage(_result())
        client = _client(fake)
        # act
        client.post("/api/chat", json={"conversation_id": "c-9", "question": "q"})
        # assert
        assert fake.calls == [("c-9", "q")]
