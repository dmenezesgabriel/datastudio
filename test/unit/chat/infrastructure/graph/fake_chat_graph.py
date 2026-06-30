import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any


class FakeChatGraph:
    """Fake compiled graph that returns a canned final state from invoke().

    An optional delay lets tests exercise the adapter's timeout path.
    """

    def __init__(self, state: dict[str, Any], *, delay_s: float = 0.0) -> None:
        self._state = state
        self._delay_s = delay_s
        self.last_input: dict[str, Any] | None = None

    def invoke(self, state: dict[str, Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.last_input = state
        if self._delay_s:
            time.sleep(self._delay_s)
        return self._state


class FakeStreamingChatGraph:
    """Fake compiled graph whose astream() yields canned ``{node: update}`` chunks.

    Mirrors LangGraph's ``stream_mode="updates"`` output. An optional per-chunk
    delay lets tests exercise the adapter's asyncio.timeout fallback.
    """

    def __init__(self, chunks: list[dict[str, Any]], *, delay_s: float = 0.0) -> None:
        self._chunks = chunks
        self._delay_s = delay_s
        self.last_input: dict[str, Any] | None = None

    async def astream(
        self, state: dict[str, Any], *args: Any, **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        self.last_input = state
        for chunk in self._chunks:
            if self._delay_s:
                await asyncio.sleep(self._delay_s)
            yield chunk
