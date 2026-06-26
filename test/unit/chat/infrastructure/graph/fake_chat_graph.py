import time
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
