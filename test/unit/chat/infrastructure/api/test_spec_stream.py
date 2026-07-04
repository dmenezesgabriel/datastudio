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
    def test_seeds_root_with_a_leading_narrative_then_sets_its_text(self) -> None:
        # The narrative is seeded (empty) at root init so it leads the F-layout; its text
        # is then set in place — narrative streams last but must render on top.
        serializer = SpecStreamSerializer()
        patches = _patches(serializer, NarrativeReady(text="Summary."))
        assert [p["path"] for p in patches] == [
            "/root",
            "/elements/root",
            "/elements/narrative",
            "/elements/narrative/props/text",
        ]
        # root's first child is the narrative, so it renders at the top
        assert patches[1]["value"]["children"] == ["narrative"]  # type: ignore[index]
        assert patches[3] == {
            "op": "replace",
            "path": "/elements/narrative/props/text",
            "value": "Summary.",
        }

    def test_narrative_element_added_once_and_text_replaced_each_time(self) -> None:
        serializer = SpecStreamSerializer()
        patches = _patches(serializer, NarrativeReady(text="Draft."), NarrativeReady(text="Done."))
        replace = [p for p in patches if p["op"] == "replace"]
        assert replace == [
            {"op": "replace", "path": "/elements/narrative/props/text", "value": "Draft."},
            {"op": "replace", "path": "/elements/narrative/props/text", "value": "Done."},
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
    def test_first_view_patch_seeds_regions_then_passes_the_line_through(self) -> None:
        serializer = SpecStreamSerializer()
        _patches(serializer, NarrativeReady(text="x"))  # root + narrative exist
        line = '{"op":"add","path":"/elements/widget-0-chart","value":{"type":"ChartJs"}}'
        out = serializer.lines_for(ViewPatchLine(line=line))
        # the KPI band + grid regions are seeded (once) ahead of the widget's own line
        paths = [json.loads(x)["path"] for x in out]
        assert paths == [
            "/elements/kpi-row",
            "/elements/root/children/-",
            "/elements/grid",
            "/elements/root/children/-",
            "/elements/widget-0-chart",
        ]
        assert out[-1] == line  # the widget's authored patch is forwarded verbatim

    def test_regions_are_seeded_only_once(self) -> None:
        serializer = SpecStreamSerializer()
        _patches(serializer, NarrativeReady(text="x"))
        first = serializer.lines_for(ViewPatchLine(line='{"op":"add","path":"/elements/a"}'))
        second = serializer.lines_for(ViewPatchLine(line='{"op":"add","path":"/elements/b"}'))
        assert any("kpi-row" in ln for ln in first)
        assert not any("kpi-row" in ln for ln in second)  # no duplicate seeding

    def test_sql_ready_sets_the_widget_frame_sql_prop(self) -> None:
        # The frame is added with the widget's view patches (they precede SqlReady), so the
        # SQL only replaces the frame's prop — mirroring how the narrative text is replaced.
        serializer = SpecStreamSerializer()
        patches = _patches(serializer, SqlReady(widget_id="widget-1", sql_query="SELECT 1"))
        assert patches == [
            {"op": "replace", "path": "/elements/widget-1-frame/props/sql", "value": "SELECT 1"}
        ]

    def test_empty_sql_emits_nothing(self) -> None:
        serializer = SpecStreamSerializer()
        assert serializer.lines_for(SqlReady(widget_id="w", sql_query="")) == []
