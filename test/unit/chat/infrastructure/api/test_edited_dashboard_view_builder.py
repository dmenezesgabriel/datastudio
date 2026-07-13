from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.infrastructure.api.edited_dashboard_view_builder import EditedDashboardViewBuilder
from shared.domain.value_objects.query_result import QueryResult


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


class TestEditedDashboardViewBuilder:
    def test_applies_a_restyle_patch_to_the_prior_spec(self) -> None:
        events: list[ChatStreamEvent] = [
            ViewPatchLine(
                line='{"op":"replace","path":"/elements/widget-0-chart/props/kind","value":"line"}'
            )
        ]
        edited = EditedDashboardViewBuilder().build(_dashboard(), events)
        assert edited.elements["widget-0-chart"].props["kind"] == "line"

    def test_applies_reanalyze_data_and_sql(self) -> None:
        result = QueryResult(columns=["n"], rows=[(7,)], row_count=1)
        events: list[ChatStreamEvent] = [
            WidgetDataReady(widget_id="widget-1", result=result),
            SqlReady(widget_id="widget-1", sql="SELECT 7"),
        ]
        edited = EditedDashboardViewBuilder().build(_dashboard(), events)
        assert edited.state is not None
        assert edited.state["widget-1"] == {"columns": ["n"], "rows": [{"n": 7}]}

    def test_leaves_the_narrative_untouched(self) -> None:
        # An edit changes widgets, not the dashboard's summary.
        events: list[ChatStreamEvent] = [NarrativeReady(text="Changed the chart.")]
        edited = EditedDashboardViewBuilder().build(_dashboard(), events)
        assert edited.elements["narrative"].props["text"] == "Summary."

    def test_returns_the_prior_spec_unchanged_for_a_no_op_edit(self) -> None:
        prior = _dashboard()
        edited = EditedDashboardViewBuilder().build(prior, [])
        assert edited is prior  # identity: caller skips recording an identical version
