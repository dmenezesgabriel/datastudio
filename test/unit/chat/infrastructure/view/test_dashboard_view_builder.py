"""Tests for the SpecStream dashboard view builder (build + edit halves).

One adapter fulfils the whole ``DashboardViewBuilder`` port: ``build`` compiles a turn's
stream events into a fresh persistable tree; ``apply_edit`` layers an edit's patches onto
an already-saved spec.
"""

import json

from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    ProgressStep,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.infrastructure.view.dashboard_view_builder import SpecStreamDashboardViewBuilder
from shared.domain.value_objects.query_result import QueryResult


def _chart_line(widget_id: str) -> str:
    # A widget's view arrives as ONE ViewPatchLine holding the newline-joined patches the
    # graph emits (see namespace_widget_patches): add the leaf, wrap it in a WidgetFrame,
    # and place the frame in the grid region.
    leaf: dict[str, object] = {
        "type": "ChartJs",
        "props": {"data": {"$state": f"/{widget_id}/rows"}},
        "children": [],
    }
    frame: dict[str, object] = {
        "type": "WidgetFrame",
        "props": {"sql": ""},
        "children": [f"{widget_id}-chart"],
    }
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
        SqlReady(widget_id="widget-0", sql="SELECT month, COUNT(*) n FROM t GROUP BY 1"),
        NarrativeReady(text="Two months."),
    ]


class TestBuild:
    def test_builds_widget_element_bound_to_persisted_state(self) -> None:
        # Act
        view = SpecStreamDashboardViewBuilder().build(_dashboard_events())
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
        view = SpecStreamDashboardViewBuilder().build(_dashboard_events())
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
        view = SpecStreamDashboardViewBuilder().build(events)
        # Assert — narrative tree, no widget state
        assert view.elements["narrative"].props.get("text") == "No dashboard here."
        assert view.state is None


def _dashboard() -> RenderTree:
    return RenderTree(
        root="root",
        elements={
            "root": RenderElement(type="Stack", props={}, children=["narrative", "grid"]),
            "narrative": RenderElement(type="Markdown", props={"text": "Summary."}, children=[]),
            "grid": RenderElement(type="Grid", props={}, children=["widget-0-frame"]),
            "widget-0-frame": RenderElement(
                type="WidgetFrame", props={"sql": "SELECT 1"}, children=["widget-0-chart"]
            ),
            "widget-0-chart": RenderElement(type="ChartJs", props={"kind": "bar"}, children=[]),
        },
        state={"widget-0": {"columns": ["m"], "rows": []}},
    )


class TestApplyEdit:
    def test_applies_a_restyle_patch_to_the_prior_spec(self) -> None:
        events: list[ChatStreamEvent] = [
            ViewPatchLine(
                line='{"op":"replace","path":"/elements/widget-0-chart/props/kind","value":"line"}'
            )
        ]
        edited = SpecStreamDashboardViewBuilder().apply_edit(_dashboard(), events)
        assert edited.elements["widget-0-chart"].props["kind"] == "line"

    def test_applies_reanalyze_data_and_sql(self) -> None:
        result = QueryResult(columns=["n"], rows=[(7,)], row_count=1)
        events: list[ChatStreamEvent] = [
            WidgetDataReady(widget_id="widget-1", result=result),
            SqlReady(widget_id="widget-1", sql="SELECT 7"),
        ]
        edited = SpecStreamDashboardViewBuilder().apply_edit(_dashboard(), events)
        assert edited.state is not None
        assert edited.state["widget-1"] == {"columns": ["n"], "rows": [{"n": 7}]}

    def test_leaves_the_narrative_untouched(self) -> None:
        # An edit changes widgets, not the dashboard's summary.
        events: list[ChatStreamEvent] = [NarrativeReady(text="Changed the chart.")]
        edited = SpecStreamDashboardViewBuilder().apply_edit(_dashboard(), events)
        assert edited.elements["narrative"].props["text"] == "Summary."

    def test_returns_the_prior_spec_unchanged_for_a_no_op_edit(self) -> None:
        prior = _dashboard()
        edited = SpecStreamDashboardViewBuilder().apply_edit(prior, [])
        assert edited is prior  # identity: caller skips recording an identical version
