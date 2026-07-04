"""Tests for compiling a turn's stream events into a persistable dashboard view."""

import json

from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    ProgressStep,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.infrastructure.api.dashboard_view_builder import DashboardViewBuilder
from shared.domain.value_objects.query_result import QueryResult


def _chart_line(widget_id: str) -> str:
    # A widget's view arrives as ONE ViewPatchLine holding the newline-joined patches the
    # graph emits (see namespace_widget_patches): add the leaf, wrap it in a WidgetFrame,
    # and place the frame in the grid region.
    leaf = {"type": "ChartJs", "props": {"data": {"$state": f"/{widget_id}/rows"}}, "children": []}
    frame = {"type": "WidgetFrame", "props": {"sql": ""}, "children": [f"{widget_id}-chart"]}
    return "\n".join(
        [
            json.dumps({"op": "add", "path": f"/elements/{widget_id}-chart", "value": leaf}),
            json.dumps({"op": "add", "path": f"/elements/{widget_id}-frame", "value": frame}),
            json.dumps(
                {"op": "add", "path": "/elements/grid/children/-", "value": f"{widget_id}-frame"}
            ),
        ]
    )


def _dashboard_events() -> list[ChatStreamEvent]:
    result = QueryResult(columns=["month", "n"], rows=[("Jan", 5), ("Feb", 9)], row_count=2)
    return [
        ProgressStep(step_id="widget-0", label="Building", status="running"),  # ignored
        WidgetDataReady(widget_id="widget-0", result=result),
        ViewPatchLine(line=_chart_line("widget-0")),
        SqlReady(widget_id="widget-0", sql_query="SELECT month, COUNT(*) n FROM t GROUP BY 1"),
        NarrativeReady(text="Two months."),
    ]


class TestDashboardViewBuilder:
    def test_builds_widget_element_bound_to_persisted_state(self) -> None:
        # Act
        view = DashboardViewBuilder().build(_dashboard_events())
        # Assert — the widget element is present, wrapped in its frame in the grid, and its
        # $state data is persisted alongside (multi-patch view line must be split, not dropped)
        assert "widget-0-chart" in view.elements
        assert view.elements["widget-0-frame"].children == ["widget-0-chart"]
        assert "widget-0-frame" in view.elements["grid"].children
        assert view.state == {
            "widget-0": {
                "columns": ["month", "n"],
                "rows": [{"month": "Jan", "n": 5}, {"month": "Feb", "n": 9}],
            }
        }

    def test_narrative_present_and_sql_set_on_the_widget_frame(self) -> None:
        # Act
        view = DashboardViewBuilder().build(_dashboard_events())
        # Assert — SQL rides the widget's frame prop (its toggle), not a separate element
        assert view.elements["narrative"].props.get("text") == "Two months."
        assert (
            view.elements["widget-0-frame"].props["sql"]
            == "SELECT month, COUNT(*) n FROM t GROUP BY 1"
        )

    def test_narrative_only_when_no_widgets(self) -> None:
        # Arrange — a plain answer with no view patches
        events: list[ChatStreamEvent] = [NarrativeReady(text="No dashboard here.")]
        # Act
        view = DashboardViewBuilder().build(events)
        # Assert — narrative tree, no widget state
        assert view.elements["narrative"].props.get("text") == "No dashboard here."
        assert view.state is None
