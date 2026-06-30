"""Tests for the incremental chat-stream events."""

import dataclasses

import pytest

from chat.domain.value_objects.stream_event import (
    NarrativeReady,
    ProgressUpdate,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from shared.domain.value_objects.query_result import QueryResult


def _result() -> QueryResult:
    return QueryResult(columns=["n"], rows=[(1,)], row_count=1)


class TestStreamEventPayloads:
    def test_progress_update_carries_stage(self) -> None:
        assert ProgressUpdate(stage="plan_widgets").stage == "plan_widgets"

    def test_widget_data_ready_carries_id_and_result(self) -> None:
        result = _result()
        event = WidgetDataReady(widget_id="widget-0", result=result)
        assert event.widget_id == "widget-0"
        assert event.result is result

    def test_view_patch_line_carries_one_jsonl_patch(self) -> None:
        line = '{"op":"add","path":"/elements/widget-0-chart","value":{}}'
        assert ViewPatchLine(line=line).line == line

    def test_sql_ready_carries_widget_id_and_query(self) -> None:
        event = SqlReady(widget_id="widget-0", sql_query="SELECT 1")
        assert event.widget_id == "widget-0"
        assert event.sql_query == "SELECT 1"

    def test_narrative_ready_carries_text(self) -> None:
        assert NarrativeReady(text="Summary.").text == "Summary."


class TestStreamEventImmutability:
    def test_widget_data_ready_is_frozen(self) -> None:
        event = WidgetDataReady(widget_id="w", result=_result())
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.widget_id = "x"  # type: ignore[misc]

    def test_view_patch_line_is_frozen(self) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            ViewPatchLine(line="{}").line = "{}"  # type: ignore[misc]
