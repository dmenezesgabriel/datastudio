from chat.domain.services.dashboard_widgets import artifact_drafts
from chat.domain.value_objects.render_tree import RenderElement, RenderTree


def _dashboard() -> RenderTree:
    return RenderTree(
        root="root",
        elements={
            "root": RenderElement(
                type="Stack", props={}, children=["narrative", "kpi-row", "grid"]
            ),
            "narrative": RenderElement(type="Markdown", props={"text": "Overview."}, children=[]),
            "kpi-row": RenderElement(type="KpiRow", props={}, children=["widget-0-frame"]),
            "grid": RenderElement(type="Grid", props={}, children=["widget-1-frame"]),
            "widget-0-frame": RenderElement(
                type="WidgetFrame", props={"sql": "SELECT count(*) c"}, children=["widget-0-kpi"]
            ),
            "widget-0-kpi": RenderElement(
                type="KpiStat", props={"label": "Total movies"}, children=[]
            ),
            "widget-1-frame": RenderElement(
                type="WidgetFrame", props={"sql": "SELECT g, n"}, children=["widget-1-chart"]
            ),
            "widget-1-chart": RenderElement(
                type="ChartJs", props={"title": "Movies by genre", "kind": "bar"}, children=[]
            ),
        },
        state={
            "widget-0": {"columns": ["c"], "rows": []},
            "widget-1": {"columns": ["g"], "rows": []},
        },
    )


def _narrative_only() -> RenderTree:
    return RenderTree(
        root="root",
        elements={
            "root": RenderElement(type="Stack", props={}, children=["narrative"]),
            "narrative": RenderElement(type="Markdown", props={"text": "Hi."}, children=[]),
        },
    )


class TestArtifactDrafts:
    def test_narrative_only_view_yields_no_drafts(self) -> None:
        assert artifact_drafts("hello", _narrative_only()) == []

    def test_yields_only_the_dashboard_draft(self) -> None:
        # One answer saves one artifact — the whole dashboard — not a separate card per
        # widget (which flooded the gallery and leaked widget ids as titles; audit MOD-2).
        drafts = artifact_drafts("Overview of movies", _dashboard())
        assert len(drafts) == 1

    def test_dashboard_draft_is_titled_by_the_question_and_carries_every_widget(self) -> None:
        dashboard = _dashboard()
        drafts = artifact_drafts("Overview of movies", dashboard)
        assert drafts[0].title == "Overview of movies"
        assert drafts[0].spec is dashboard  # the full dashboard, unchanged
        # Nothing is dropped — both widgets remain on the single saved dashboard.
        assert {"widget-0-frame", "widget-1-frame"} <= set(drafts[0].spec.elements)
