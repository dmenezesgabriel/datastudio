"""Tests for ObservableNode's structured logging and log-safe field extraction."""

import json
import logging

from chat.domain.value_objects.widget import WidgetResult, WidgetSpec
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.observable_node import ObservableNode
from shared.domain.value_objects.query_result import QueryResult
from shared.infrastructure.logging.json_formatter import JsonFormatter


class _StubNode:
    """A graph node whose output is a fixed partial-state dict."""

    def __init__(self, result: dict[str, object]) -> None:
        self._result = result

    def __call__(self, state: ChatState) -> dict[str, object]:
        return self._result


def _emitted_extra(caplog: object, result: dict[str, object]) -> dict[str, object]:
    """Run an ObservableNode over a stub and return the emitted record's extra fields."""
    node = ObservableNode("build_widget", _StubNode(result))
    node({"request_id": "r-1"})  # type: ignore[arg-type]
    record = caplog.records[-1]  # type: ignore[attr-defined]
    stdlib = JsonFormatter._STDLIB_ATTRS | {"request_id", "duration_ms", "taskName"}
    return {k: v for k, v in record.__dict__.items() if k not in stdlib}


class TestLogSafeExtraction:
    def test_summarizes_widget_channels_as_counts(self, caplog: object) -> None:
        # Arrange — build_widget emits the aggregation channels, not scalars
        qr = QueryResult(columns=["n"], rows=[(1,)], row_count=1)
        result: dict[str, object] = {
            "widget_results": [WidgetResult(widget_id="w0", title="T", result=qr, sql="SELECT 1")],
            "widget_patch_lines": ['{"op":"add","path":"/elements/w0-kpi","value":{}}'],
        }
        # Act
        with caplog.at_level(logging.INFO):  # type: ignore[attr-defined]
            extra = _emitted_extra(caplog, result)
        # Assert — non-JSON-native value objects are reduced to counts
        assert extra["widget_count"] == 1
        assert extra["view_patch_count"] == 1
        assert "widget_results" not in extra

    def test_summarizes_planned_widget_specs_as_count(self, caplog: object) -> None:
        # Arrange
        result: dict[str, object] = {
            "widget_specs": [
                WidgetSpec(id="widget-0", title="T", sub_question="q", role="analysis")
            ]
        }
        # Act
        with caplog.at_level(logging.INFO):  # type: ignore[attr-defined]
            extra = _emitted_extra(caplog, result)
        # Assert
        assert extra["planned_widget_count"] == 1
        assert "widget_specs" not in extra

    def test_emitted_record_is_json_serializable(self, caplog: object) -> None:
        # Regression: WidgetResult in the log extra once raised TypeError in the
        # JSON formatter and dropped the build_widget.complete log line entirely.
        # Arrange
        qr = QueryResult(columns=["n"], rows=[(1,)], row_count=1)
        result: dict[str, object] = {
            "widget_results": [WidgetResult(widget_id="w0", title="T", result=qr, sql="SELECT 1")],
        }
        node = ObservableNode("build_widget", _StubNode(result))
        # Act
        with caplog.at_level(logging.INFO):  # type: ignore[attr-defined]
            node({"request_id": "r-1"})  # type: ignore[arg-type]
        # Assert — the formatter serializes the record without raising
        line = JsonFormatter().format(caplog.records[-1])  # type: ignore[attr-defined]
        assert json.loads(line)["message"] == "build_widget.complete"
