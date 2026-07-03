"""Tests for translating engine stream events into json-render SpecStream lines."""

import json
from datetime import date, datetime
from decimal import Decimal

from chat.domain.value_objects.stream_event import (
    NarrativeReady,
    ProgressStep,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.infrastructure.api.spec_stream import SpecStreamSerializer
from shared.domain.value_objects.query_result import QueryResult


def _patches(serializer: SpecStreamSerializer, *events: object) -> list[dict[str, object]]:
    lines: list[dict[str, object]] = []
    for event in events:
        for line in serializer.lines_for(event):  # type: ignore[arg-type]
            lines.append(json.loads(line))
    return lines


class TestNarrative:
    def test_initializes_root_and_adds_markdown(self) -> None:
        serializer = SpecStreamSerializer()
        patches = _patches(serializer, NarrativeReady(text="Summary."))
        assert [p["path"] for p in patches] == [
            "/root",
            "/elements/root",
            "/elements/narrative",
            "/elements/root/children/-",
        ]
        assert patches[2]["value"]["props"]["text"] == "Summary."  # type: ignore[index]

    def test_narrative_is_added_once_then_replaced_in_place(self) -> None:
        serializer = SpecStreamSerializer()
        patches = _patches(serializer, NarrativeReady(text="Draft."), NarrativeReady(text="Done."))
        replace = [p for p in patches if p["op"] == "replace"]
        assert replace == [
            {"op": "replace", "path": "/elements/narrative/props/text", "value": "Done."}
        ]
        assert sum(1 for p in patches if p["path"] == "/elements/narrative") == 1


class TestProgress:
    def test_first_step_initializes_channel_and_adds_step(self) -> None:
        # Arrange / Act — a step never seen before
        serializer = SpecStreamSerializer()
        patches = _patches(
            serializer, ProgressStep(step_id="get_schema", label="Reading", status="running")
        )
        # Assert — the /state/progress map is created once (json-render only applies /state
        # and /elements patches), then the step is added with order 0
        assert patches[0] == {"op": "add", "path": "/state/progress", "value": {}}
        assert patches[1] == {
            "op": "add",
            "path": "/state/progress/get_schema",
            "value": {"label": "Reading", "status": "running", "parentId": None, "order": 0},
        }

    def test_repeat_step_replaces_only_its_status(self) -> None:
        # Arrange — the same step id transitions running → done
        serializer = SpecStreamSerializer()
        patches = _patches(
            serializer,
            ProgressStep(step_id="get_schema", label="Reading", status="running"),
            ProgressStep(step_id="get_schema", label="Reading", status="done"),
        )
        # Assert — the map init/add happen once; the second sighting only flips status
        assert patches[-1] == {
            "op": "replace",
            "path": "/state/progress/get_schema/status",
            "value": "done",
        }
        assert sum(1 for p in patches if p["path"] == "/state/progress") == 1

    def test_child_step_carries_parent_and_incrementing_order(self) -> None:
        # Arrange — a parent step then its nested child
        serializer = SpecStreamSerializer()
        patches = _patches(
            serializer,
            ProgressStep(step_id="widget-0", label='Building "T"', status="running"),
            ProgressStep(
                step_id="widget-0:sql",
                label="Generating SQL",
                status="running",
                parent_id="widget-0",
            ),
        )
        child = next(p for p in patches if p["path"] == "/state/progress/widget-0:sql")
        assert child["value"]["parentId"] == "widget-0"  # type: ignore[index]
        assert child["value"]["order"] == 1  # type: ignore[index]


class TestWidgetData:
    def test_streams_rows_as_a_state_patch(self) -> None:
        # Arrange — the data is delivered as a backend /state patch, never an /elements one
        serializer = SpecStreamSerializer()
        result = QueryResult(
            columns=["month", "rev"], rows=[("Jan", 100), ("Feb", 200)], row_count=2
        )
        # Act
        patches = _patches(serializer, WidgetDataReady(widget_id="widget-0", result=result))
        # Assert
        assert len(patches) == 1
        assert patches[0]["op"] == "add"
        assert patches[0]["path"] == "/state/widget-0"
        assert patches[0]["value"] == {
            "columns": ["month", "rev"],
            "rows": [{"month": "Jan", "rev": 100}, {"month": "Feb", "rev": 200}],
        }

    def test_caps_streamed_rows(self) -> None:
        serializer = SpecStreamSerializer()
        rows = [(i,) for i in range(600)]
        result = QueryResult(columns=["n"], rows=rows, row_count=600)
        patches = _patches(serializer, WidgetDataReady(widget_id="w", result=result))
        assert len(patches[0]["value"]["rows"]) == 500  # type: ignore[index]

    def test_serializes_temporal_and_decimal_cells_to_json_native(self) -> None:
        # Regression: a date/datetime/Decimal cell (DuckDB returns these for date and
        # exact-numeric columns) once raised TypeError and sank the whole stream.
        # Arrange
        serializer = SpecStreamSerializer()
        result = QueryResult(
            columns=["day", "ts", "amount"],
            rows=[(date(2012, 1, 1), datetime(2012, 1, 1, 9, 30), Decimal("12.50"))],
            row_count=1,
        )
        # Act
        patches = _patches(serializer, WidgetDataReady(widget_id="w0", result=result))
        # Assert — temporals become ISO strings, Decimal becomes a float
        assert patches[0]["value"]["rows"][0] == {  # type: ignore[index]
            "day": "2012-01-01",
            "ts": "2012-01-01T09:30:00",
            "amount": 12.5,
        }


class TestViewAndSql:
    def test_view_patch_line_passes_through(self) -> None:
        serializer = SpecStreamSerializer()
        _patches(serializer, NarrativeReady(text="x"))  # root exists
        line = '{"op":"add","path":"/elements/widget-0-chart","value":{"type":"ChartJs"}}'
        assert serializer.lines_for(ViewPatchLine(line=line)) == [line]

    def test_sql_ready_emits_per_widget_fenced_markdown(self) -> None:
        serializer = SpecStreamSerializer()
        _patches(serializer, NarrativeReady(text="x"))
        patches = _patches(serializer, SqlReady(widget_id="widget-1", sql_query="SELECT 1"))
        sql = next(p for p in patches if p["path"] == "/elements/widget-1-sql")
        assert "```sql" in sql["value"]["props"]["text"]  # type: ignore[index]
        assert "SELECT 1" in sql["value"]["props"]["text"]  # type: ignore[index]

    def test_empty_sql_emits_nothing(self) -> None:
        serializer = SpecStreamSerializer()
        assert serializer.lines_for(SqlReady(widget_id="w", sql_query="")) == []
