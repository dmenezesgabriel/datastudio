"""Tests for the ProgressNode proxy — running/done on success, failed on error."""

from typing import Any, cast

import pytest

from chat.domain.value_objects.stream_event import ProgressStep
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.progress_node import ProgressNode


class RecordingReporter:
    """Captures every ProgressStep reported, in order, for assertions."""

    def __init__(self) -> None:
        self.steps: list[ProgressStep] = []

    def report(self, step: ProgressStep) -> None:
        self.steps.append(step)


def _state() -> ChatState:
    return cast(ChatState, {"question": "q", "history": []})


class TestProgressNodeSuccess:
    def test_reports_running_then_done_around_the_inner_node(self) -> None:
        # arrange
        reporter = RecordingReporter()
        node = ProgressNode(
            "get_schema", "Reading the schema", reporter, lambda _s: {"schema": "x"}
        )
        # act
        result = node(_state())
        # assert — running then done, and the inner result is passed through untouched
        assert [(s.step_id, s.status) for s in reporter.steps] == [
            ("get_schema", "running"),
            ("get_schema", "done"),
        ]
        assert result == {"schema": "x"}


class TestProgressNodeFailure:
    def test_reports_failed_and_re_raises_when_the_inner_node_raises(self) -> None:
        # arrange — an inner node that raises (e.g. a bug the RetryPolicy won't retry)
        reporter = RecordingReporter()

        def _boom(_state: ChatState) -> Any:
            raise ValueError("schema fetch broke")

        node = ProgressNode("get_schema", "Reading the schema", reporter, _boom)
        # act / assert — the error still propagates so LangGraph's RetryPolicy governs it
        with pytest.raises(ValueError, match="schema fetch broke"):
            node(_state())
        # and the checklist ends on failed, never a stale running/done
        assert [(s.step_id, s.status) for s in reporter.steps] == [
            ("get_schema", "running"),
            ("get_schema", "failed"),
        ]
