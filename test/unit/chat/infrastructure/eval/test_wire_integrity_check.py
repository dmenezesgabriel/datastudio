"""Unit tests for WireIntegrityCheck — the only check that grades the real SpecStream."""

import json
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.eval.wire_integrity_check import WireIntegrityCheck
from chat.infrastructure.graph.chat_state import ChatState
from shared.domain.value_objects.query_result import QueryResult


def _kpi_line(widget_id: str, component: str = "KpiStat") -> str:
    """A namespaced view patch binding a widget's data via $state."""
    element = {
        "type": component,
        "props": {"label": "Total", "valueColumn": "n", "data": {"$state": f"/{widget_id}/rows"}},
        "children": [],
    }
    return json.dumps({"op": "add", "path": f"/elements/{widget_id}-kpi", "value": element})


def _child_line(child_id: str) -> str:
    """Append an element id to the root Stack's children."""
    return json.dumps({"op": "add", "path": "/elements/root/children/-", "value": child_id})


def _frame_lines(widget_id: str, region: str = "kpi-row") -> list[str]:
    """Wrap the widget's leaf in its WidgetFrame and place the frame in a region.

    Mirrors what namespace_widget_patches emits, so the frame exists when the SqlReady
    event replaces its ``sql`` prop (as it does on the real wire).
    """
    frame = {"type": "WidgetFrame", "props": {"sql": ""}, "children": [f"{widget_id}-kpi"]}
    return [
        json.dumps({"op": "add", "path": f"/elements/{widget_id}-frame", "value": frame}),
        json.dumps(
            {"op": "add", "path": f"/elements/{region}/children/-", "value": f"{widget_id}-frame"}
        ),
    ]


def _state(results: list[WidgetResult], views: list[str], response: str = "Answer.") -> ChatState:
    raw: dict[str, Any] = {
        "widget_results": results,
        "widget_patch_lines": views,
        "response": response,
    }
    return raw  # type: ignore[return-value]


def _widget(widget_id: str, result: QueryResult, sql: str = "SELECT 42 AS n") -> WidgetResult:
    return WidgetResult(widget_id=widget_id, title="Total", result=result, sql=sql)


class TestWireIntegrityValid:
    def test_valid_stream_passes(self) -> None:
        result = QueryResult(columns=["n"], rows=[(42,)], row_count=1)
        views = [_kpi_line("widget-0"), *_frame_lines("widget-0")]
        check = WireIntegrityCheck().evaluate(_state([_widget("widget-0", result)], views))
        assert check["passed"] is True
        assert check["type"] == "wire_integrity"

    def test_temporal_and_decimal_cells_do_not_break_the_wire(self) -> None:
        # Regression guard: date/Decimal cells must serialize (via _json_default), not crash.
        result = QueryResult(
            columns=["day", "amount"], rows=[(date(2024, 1, 1), Decimal("1.50"))], row_count=1
        )
        views = [_kpi_line("widget-0"), *_frame_lines("widget-0")]
        check = WireIntegrityCheck().evaluate(_state([_widget("widget-0", result)], views))
        assert check["passed"] is True


class TestWireIntegrityBites:
    def test_non_catalogue_component_type_fails(self) -> None:
        result = QueryResult(columns=["n"], rows=[(42,)], row_count=1)
        views = [_kpi_line("widget-0", component="BadWidget"), _child_line("widget-0-kpi")]
        # sql="" so no SqlReady frame patch — the non-catalogue leaf is the isolated failure.
        check = WireIntegrityCheck().evaluate(_state([_widget("widget-0", result, sql="")], views))
        assert check["passed"] is False
        assert "non-catalogue" in check["reasoning"]

    def test_binding_without_streamed_data_fails(self) -> None:
        # View authored against /widget-0/rows but no widget produced data → nothing streamed.
        views = [_kpi_line("widget-0"), _child_line("widget-0-kpi")]
        check = WireIntegrityCheck().evaluate(_state([], views))
        assert check["passed"] is False
        assert "no data streamed" in check["reasoning"]

    def test_dangling_child_reference_fails(self) -> None:
        result = QueryResult(columns=["n"], rows=[(42,)], row_count=1)
        views = [_child_line("ghost")]  # references an element that is never added
        # sql="" so no SqlReady frame patch — the dangling child is the isolated failure.
        check = WireIntegrityCheck().evaluate(_state([_widget("widget-0", result, sql="")], views))
        assert check["passed"] is False
        assert "missing child" in check["reasoning"]

    def test_serializer_failure_is_reported_not_raised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # If the serializer ever crashes (e.g. a future unhandled cell type), the check must
        # fail gracefully rather than blow up the whole eval run.
        def _boom(self: object, event: object) -> list[str]:
            raise TypeError("Object of type X is not JSON serializable")

        monkeypatch.setattr(
            "chat.infrastructure.eval.wire_integrity_check.SpecStreamSerializer.lines_for", _boom
        )
        result = QueryResult(columns=["n"], rows=[(42,)], row_count=1)
        check = WireIntegrityCheck().evaluate(_state([_widget("widget-0", result)], []))
        assert check["passed"] is False
        assert "serialize/apply" in check["reasoning"]
