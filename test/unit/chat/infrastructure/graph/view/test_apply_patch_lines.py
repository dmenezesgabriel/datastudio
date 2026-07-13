import json

from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.infrastructure.graph.view.render_tree_builder import apply_patch_lines


def _dashboard() -> RenderTree:
    return RenderTree(
        root="root",
        elements={
            "root": RenderElement(type="Stack", props={}, children=["grid"]),
            "grid": RenderElement(
                type="Grid", props={}, children=["widget-0-frame", "widget-1-frame"]
            ),
            "widget-0-frame": RenderElement(
                type="WidgetFrame", props={"sql": "SELECT 1"}, children=["widget-0-chart"]
            ),
            "widget-0-chart": RenderElement(
                type="ChartJs", props={"kind": "bar", "title": "Revenue"}, children=[]
            ),
            "widget-1-frame": RenderElement(
                type="WidgetFrame", props={"sql": "SELECT 2"}, children=["widget-1-table"]
            ),
            "widget-1-table": RenderElement(type="DataTable", props={}, children=[]),
        },
        state={"widget-0": {"columns": ["m"], "rows": []}},
    )


def _line(op: str, path: str, value: object = None) -> str:
    return json.dumps({"op": op, "path": path, "value": value})


class TestRestylePatches:
    def test_replaces_a_chart_kind_without_touching_other_widgets(self) -> None:
        edited = apply_patch_lines(
            _dashboard(), [_line("replace", "/elements/widget-0-chart/props/kind", "line")]
        )
        assert edited.elements["widget-0-chart"].props["kind"] == "line"
        assert edited.elements["widget-1-table"].type == "DataTable"  # untouched

    def test_reorders_a_regions_children(self) -> None:
        edited = apply_patch_lines(
            _dashboard(),
            [_line("replace", "/elements/grid/children", ["widget-1-frame", "widget-0-frame"])],
        )
        assert edited.elements["grid"].children == ["widget-1-frame", "widget-0-frame"]


class TestReanalyzePatches:
    def test_adds_new_widget_state(self) -> None:
        edited = apply_patch_lines(
            _dashboard(), [_line("add", "/state/widget-2", {"columns": ["c"], "rows": []})]
        )
        assert edited.state is not None
        assert edited.state["widget-2"] == {"columns": ["c"], "rows": []}

    def test_dedupes_a_child_append_for_a_reused_widget_id(self) -> None:
        # A reanalyzed widget reuses its id: the frame element is overwritten, but re-appending
        # its already-present frame ref to the region must not duplicate it.
        edited = apply_patch_lines(
            _dashboard(), [_line("add", "/elements/grid/children/-", "widget-0-frame")]
        )
        assert edited.elements["grid"].children == ["widget-0-frame", "widget-1-frame"]

    def test_appends_a_genuinely_new_child(self) -> None:
        edited = apply_patch_lines(
            _dashboard(), [_line("add", "/elements/grid/children/-", "widget-2-frame")]
        )
        assert edited.elements["grid"].children[-1] == "widget-2-frame"

    def test_replaces_a_frame_sql(self) -> None:
        edited = apply_patch_lines(
            _dashboard(), [_line("replace", "/elements/widget-0-frame/props/sql", "SELECT 99")]
        )
        assert edited.elements["widget-0-frame"].props["sql"] == "SELECT 99"


class TestPatchResilience:
    def test_removes_an_element(self) -> None:
        edited = apply_patch_lines(_dashboard(), [_line("remove", "/elements/widget-1-table")])
        assert "widget-1-table" not in edited.elements

    def test_ignores_malformed_lines(self) -> None:
        edited = apply_patch_lines(_dashboard(), ["not json", _line("replace", "no-slash", "x")])
        assert edited.elements["widget-0-chart"].props["kind"] == "bar"  # unchanged

    def test_seeds_state_when_the_base_had_none(self) -> None:
        base = RenderTree(
            root="root", elements={"root": RenderElement(type="Stack", props={}, children=[])}
        )
        edited = apply_patch_lines(base, [_line("add", "/state/widget-0", {"rows": []})])
        assert edited.state == {"widget-0": {"rows": []}}
