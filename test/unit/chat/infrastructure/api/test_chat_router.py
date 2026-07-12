import json
from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chat.application.use_cases.stream_message import StreamMessage
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.infrastructure.api.chat_router import ChatRouter
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.api.fakes import FakeCurrentUser


class FakeStreamMessage:
    """Records calls and yields fixed events instead of running the graph."""

    def __init__(self, events: list[ChatStreamEvent]) -> None:
        self._events = events
        self.calls: list[tuple[str, str, str]] = []

    async def execute(
        self, owner_id: str, conversation_id: str, question: str
    ) -> AsyncIterator[ChatStreamEvent]:
        self.calls.append((owner_id, conversation_id, question))
        for event in self._events:
            yield event


def _client(fake: FakeStreamMessage, user_id: str = "u-1") -> TestClient:
    app = FastAPI()
    app.include_router(ChatRouter(cast(StreamMessage, fake), FakeCurrentUser(user_id)).router)
    return TestClient(app)


def _events() -> list[ChatStreamEvent]:
    result = QueryResult(columns=["n"], rows=[(42,)], row_count=1)
    chart = '{"op":"add","path":"/elements/widget-0-chart","value":{"type":"ChartJs"}}'
    return [
        WidgetDataReady(widget_id="widget-0", result=result),
        ViewPatchLine(line=chart),
        SqlReady(widget_id="widget-0", sql="SELECT count(*) FROM orders"),
        NarrativeReady(text="There are 42 orders."),
    ]


def _stream_lines(client: TestClient, body: dict[str, object]) -> list[dict[str, object]]:
    with client.stream("POST", "/api/chat", json=body) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


class TestChatRouterStreaming:
    def test_streams_state_and_element_patches(self) -> None:
        # arrange
        client = _client(FakeStreamMessage(_events()))
        # act
        patches = _stream_lines(
            client, {"prompt": "How many orders?", "context": {"conversation_id": "c-1"}}
        )
        # assert — every line is an RFC-6902 patch
        assert all("op" in p and "path" in p for p in patches)
        # the data is delivered as a /state patch (out of the model), the chart as /elements
        state = next(p for p in patches if p["path"] == "/state/widget-0")
        assert state["value"]["rows"] == [{"n": 42}]  # type: ignore[index]
        chart = next(p for p in patches if p["path"] == "/elements/widget-0-chart")
        assert chart["value"]["type"] == "ChartJs"  # type: ignore[index]
        # the narrative element is seeded empty (to lead the F-layout) then its text is set
        narrative_text = next(p for p in patches if p["path"] == "/elements/narrative/props/text")
        assert narrative_text["value"] == "There are 42 orders."

    def test_no_element_patch_carries_row_data(self) -> None:
        # the rows must reach the client ONLY via /state, never inside an /elements patch
        # (the narrative may legitimately say "42 orders"; the row object must not appear)
        client = _client(FakeStreamMessage(_events()))
        patches = _stream_lines(client, {"prompt": "q", "context": {"conversation_id": "c-1"}})
        element_blobs = json.dumps([p for p in patches if str(p["path"]).startswith("/elements")])
        assert '"n"' not in element_blobs  # the result column key only appears under /state

    def test_passes_owner_and_conversation_id_to_use_case(self) -> None:
        fake = FakeStreamMessage(_events())
        _stream_lines(
            _client(fake, "alice"), {"prompt": "q", "context": {"conversation_id": "c-9"}}
        )
        # the owner comes from the resolved current user, not the request body
        assert fake.calls == [("alice", "c-9", "q")]

    def test_missing_conversation_id_still_streams(self) -> None:
        fake = FakeStreamMessage(_events())
        patches = _stream_lines(_client(fake), {"prompt": "q"})
        assert patches
        assert fake.calls[0][2] == "q"
