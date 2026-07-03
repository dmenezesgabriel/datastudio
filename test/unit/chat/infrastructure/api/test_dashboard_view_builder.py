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
    # A widget's view arrives as ONE ViewPatchLine holding TWO newline-joined patches:
    # add the element, then append it to the root's children (as the real graph emits).
    element = {
        "type": "ChartJs",
        "props": {"data": {"$state": f"/{widget_id}/rows"}},
        "children": [],
    }
    add_element = json.dumps(
        {"op": "add", "path": f"/elements/{widget_id}-chart", "value": element}
    )
    add_child = json.dumps(
        {"op": "add", "path": "/elements/root/children/-", "value": f"{widget_id}-chart"}
    )
    return add_element + "\n" + add_child


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
        # Assert — the widget element is present, wired into the root, and its $state data
        # is persisted alongside (multi-patch view line must be split, not dropped)
        assert "widget-0-chart" in view.elements
        assert "widget-0-chart" in view.elements["root"].children
        assert view.state == {
            "widget-0": {
                "columns": ["month", "n"],
                "rows": [{"month": "Jan", "n": 5}, {"month": "Feb", "n": 9}],
            }
        }

    def test_includes_narrative_and_sql_disclosure(self) -> None:
        # Act
        view = DashboardViewBuilder().build(_dashboard_events())
        # Assert
        assert view.elements["narrative"].props.get("text") == "Two months."
        assert any("```sql" in str(e.props.get("text", "")) for e in view.elements.values())

    def test_narrative_only_when_no_widgets(self) -> None:
        # Arrange — a plain answer with no view patches
        events: list[ChatStreamEvent] = [NarrativeReady(text="No dashboard here.")]
        # Act
        view = DashboardViewBuilder().build(events)
        # Assert — narrative tree, no widget state
        assert view.elements["narrative"].props.get("text") == "No dashboard here."
        assert view.state is None
