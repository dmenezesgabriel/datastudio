from decimal import Decimal

from chat.domain.value_objects.view_spec import ChartSpec, KpiSpec, ViewSpec
from chat.infrastructure.graph.view.render_tree_builder import (
    _format_value,
    assemble_render_tree,
    build_chart_element,
    build_kpi_element,
    build_markdown_element,
    build_table_element,
    narrative_tree,
)
from shared.domain.value_objects.query_result import QueryResult


def _result() -> QueryResult:
    return QueryResult(
        columns=["month", "revenue"],
        rows=[("Jan", 100), ("Feb", 200)],
        row_count=2,
    )


def _single_row() -> QueryResult:
    return QueryResult(columns=["month", "revenue"], rows=[("Jan", 100)], row_count=1)


class TestAssembleRenderTree:
    def test_builds_narrative_kpi_chart_and_table_in_order(self) -> None:
        # arrange — a single-row result so the KPI is meaningful
        spec = ViewSpec(
            kpis=[KpiSpec(label="Total", value_column="revenue")],
            charts=[
                ChartSpec(
                    kind="bar", title="Revenue", label_column="month", value_columns=["revenue"]
                )
            ],
            show_table=True,
        )
        # act
        tree = assemble_render_tree(spec, _single_row(), "Revenue grew.")
        # assert
        assert tree.root == "root"
        assert tree.elements["root"].children == ["narrative", "kpi-0", "chart-0", "table"]
        assert tree.elements["narrative"].props["text"] == "Revenue grew."

    def test_drops_kpi_on_multi_row_result(self) -> None:
        # arrange — a KPI is ambiguous across many rows, so it is omitted
        spec = ViewSpec(
            kpis=[KpiSpec(label="Total", value_column="revenue")],
            charts=[],
            show_table=True,
        )
        # act
        tree = assemble_render_tree(spec, _result(), "answer")
        # assert
        assert tree.elements["root"].children == ["narrative", "table"]

    def test_root_element_type_is_stack(self) -> None:
        # kills mutmut_52 ("XXStackXX"), mutmut_53 ("stack"), mutmut_54 ("STACK")
        spec = ViewSpec(kpis=[], charts=[], show_table=False)
        tree = assemble_render_tree(spec, _result(), "ok")
        assert tree.elements["root"].type == "Stack"

    def test_table_stored_under_table_key(self) -> None:
        # kills mutmut_37 ("XXtableXX"), mutmut_38 ("TABLE")
        spec = ViewSpec(kpis=[], charts=[], show_table=True)
        tree = assemble_render_tree(spec, _result(), "ok")
        assert "table" in tree.elements
        assert "XXtableXX" not in tree.elements
        assert "TABLE" not in tree.elements

    def test_drops_chart_referencing_missing_column(self) -> None:
        # arrange — one valid chart, one referencing a column not in the result
        spec = ViewSpec(
            kpis=[],
            charts=[
                ChartSpec(kind="bar", title="ok", label_column="month", value_columns=["revenue"]),
                ChartSpec(kind="bar", title="bad", label_column="month", value_columns=["missing"]),
            ],
            show_table=False,
        )
        # act
        tree = assemble_render_tree(spec, _result(), "answer")
        # assert — only the valid chart survives; narrative always present
        assert tree.elements["root"].children == ["narrative", "chart-0"]
        assert "chart-1" not in tree.elements


class TestBuildKpiElement:
    def test_uses_single_row_value(self) -> None:
        # act
        element = build_kpi_element(KpiSpec(label="Total", value_column="revenue"), _single_row())
        # assert
        assert element is not None
        assert element.props == {"label": "Total", "value": "100"}

    def test_element_type_is_kpi_stat(self) -> None:
        # kills mutmut_24 ("XXKpiStatXX"), mutmut_25 ("kpistat"), mutmut_26 ("KPISTAT")
        element = build_kpi_element(KpiSpec(label="Total", value_column="revenue"), _single_row())
        assert element is not None
        assert element.type == "KpiStat"

    def test_returns_none_for_missing_column(self) -> None:
        # act
        element = build_kpi_element(KpiSpec(label="x", value_column="missing"), _single_row())
        # assert
        assert element is None

    def test_returns_none_for_multi_row_result(self) -> None:
        # arrange — row 0 of a many-row result is not an unambiguous headline figure
        element = build_kpi_element(KpiSpec(label="Total", value_column="revenue"), _result())
        # assert
        assert element is None

    def test_formats_large_numbers_with_thousands_separators(self) -> None:
        # arrange
        result = QueryResult(columns=["total"], rows=[(1234567,)], row_count=1)
        # act
        element = build_kpi_element(KpiSpec(label="Orders", value_column="total"), result)
        # assert
        assert element is not None
        assert element.props["value"] == "1,234,567"


class TestBuildChartElement:
    def test_maps_labels_and_datasets(self) -> None:
        # act
        element = build_chart_element(
            ChartSpec(kind="line", title="t", label_column="month", value_columns=["revenue"]),
            _result(),
        )
        # assert
        assert element is not None
        assert element.props["labels"] == ["Jan", "Feb"]
        assert element.props["datasets"] == [{"label": "revenue", "data": [100, 200]}]

    def test_element_type_is_chart_js(self) -> None:
        # kills mutmut_47 ("XXChartJsXX"), mutmut_48 ("chartjs"), mutmut_49 ("CHARTJS")
        element = build_chart_element(
            ChartSpec(kind="bar", title="t", label_column="month", value_columns=["revenue"]),
            _result(),
        )
        assert element is not None
        assert element.type == "ChartJs"

    def test_props_use_lowercase_kind_and_title_keys(self) -> None:
        # kills mutmut_33 ("KIND"), mutmut_34 ("XXtitleXX"), mutmut_35 ("TITLE")
        element = build_chart_element(
            ChartSpec(kind="bar", title="Monthly", label_column="month", value_columns=["revenue"]),
            _result(),
        )
        assert element is not None
        assert "kind" in element.props
        assert "title" in element.props
        assert element.props["kind"] == "bar"
        assert element.props["title"] == "Monthly"

    def test_returns_none_when_label_column_missing(self) -> None:
        # act
        element = build_chart_element(
            ChartSpec(kind="bar", title="t", label_column="missing", value_columns=["revenue"]),
            _result(),
        )
        # assert
        assert element is None

    def test_skips_rows_with_null_label(self) -> None:
        # arrange — heterogeneous UNION-ALL result: only some rows carry this label
        result = QueryResult(
            columns=["payment_type", "revenue"],
            rows=[(None, 252.24), ("credit_card", 900.0), (None, 19.6), ("boleto", 300.0)],
            row_count=4,
        )
        # act
        element = build_chart_element(
            ChartSpec(
                kind="pie", title="t", label_column="payment_type", value_columns=["revenue"]
            ),
            result,
        )
        # assert — null-label rows are excluded so no "None" slices appear
        assert element is not None
        assert element.props["labels"] == ["credit_card", "boleto"]
        assert element.props["datasets"] == [{"label": "revenue", "data": [900.0, 300.0]}]

    def test_returns_none_when_all_labels_null(self) -> None:
        # arrange
        result = QueryResult(columns=["k", "v"], rows=[(None, 1), (None, 2)], row_count=2)
        # act
        element = build_chart_element(
            ChartSpec(kind="bar", title="t", label_column="k", value_columns=["v"]),
            result,
        )
        # assert
        assert element is None


class TestBuildMarkdownElement:
    def test_type_is_markdown(self) -> None:
        element = build_markdown_element("hello")
        assert element.type == "Markdown"

    def test_text_prop_matches_input(self) -> None:
        element = build_markdown_element("hello")
        assert element.props["text"] == "hello"

    def test_no_children(self) -> None:
        assert build_markdown_element("x").children == []


class TestBuildTableElement:
    def test_type_is_data_table(self) -> None:
        result = QueryResult(columns=["a", "b"], rows=[(1, 2)], row_count=1)
        assert build_table_element(result).type == "DataTable"

    def test_columns_prop_matches_result(self) -> None:
        result = QueryResult(columns=["x", "y"], rows=[], row_count=0)
        element = build_table_element(result)
        assert element.props["columns"] == ["x", "y"]

    def test_rows_prop_contains_all_rows(self) -> None:
        result = QueryResult(columns=["n"], rows=[(1,), (2,)], row_count=2)
        element = build_table_element(result)
        assert element.props["rows"] == [[1], [2]]


class TestNarrativeTree:
    def test_contains_only_narrative_under_root(self) -> None:
        # act
        tree = narrative_tree("Could not answer.")
        # assert
        assert tree.elements["root"].children == ["narrative"]
        assert tree.elements["narrative"].props["text"] == "Could not answer."

    def test_root_element_type_is_stack(self) -> None:
        tree = narrative_tree("x")
        assert tree.elements["root"].type == "Stack"

    def test_root_key_is_root(self) -> None:
        tree = narrative_tree("x")
        assert tree.root == "root"


class TestFormatValue:
    def test_int_gets_thousands_separator(self) -> None:
        assert _format_value(1234567) == "1,234,567"

    def test_float_gets_two_decimal_places(self) -> None:
        assert _format_value(1234.5) == "1,234.50"

    def test_decimal_gets_two_decimal_places(self) -> None:
        assert _format_value(Decimal("9.99")) == "9.99"

    def test_bool_true_formats_as_string(self) -> None:
        # bool is subclass of int; must be handled before int branch
        assert _format_value(True) == "True"

    def test_string_returns_as_is(self) -> None:
        assert _format_value("hello") == "hello"
