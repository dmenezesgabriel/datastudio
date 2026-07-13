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

    def test_yields_the_dashboard_plus_one_draft_per_widget(self) -> None:
        drafts = artifact_drafts("Overview of movies", _dashboard())
        assert len(drafts) == 3  # the dashboard + 2 widgets

    def test_dashboard_draft_is_first_titled_by_the_question(self) -> None:
        dashboard = _dashboard()
        drafts = artifact_drafts("Overview of movies", dashboard)
        assert drafts[0].title == "Overview of movies"
        assert drafts[0].spec is dashboard  # the full dashboard, unchanged

    def test_widget_drafts_are_titled_by_chart_title_or_kpi_label(self) -> None:
        titles = {d.title for d in artifact_drafts("q", _dashboard())[1:]}
        assert titles == {"Total movies", "Movies by genre"}


class TestSingleWidgetSpec:
    def _widget_spec(self, widget_title: str) -> RenderTree:
        drafts = artifact_drafts("q", _dashboard())
        return next(d.spec for d in drafts if d.title == widget_title)

    def test_contains_only_that_widgets_elements(self) -> None:
        spec = self._widget_spec("Movies by genre")
        assert set(spec.elements) == {"root", "widget-1-frame", "widget-1-chart"}
        assert "narrative" not in spec.elements
        assert "widget-0-kpi" not in spec.elements

    def test_root_stack_holds_the_widget_frame(self) -> None:
        spec = self._widget_spec("Movies by genre")
        assert spec.root == "root"
        assert spec.elements["root"].children == ["widget-1-frame"]

    def test_carries_only_that_widgets_state(self) -> None:
        spec = self._widget_spec("Movies by genre")
        assert spec.state == {"widget-1": {"columns": ["g"], "rows": []}}
