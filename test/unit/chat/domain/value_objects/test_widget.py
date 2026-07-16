"""Tests for the dashboard widget value objects."""

import dataclasses

import pytest

from chat.domain.value_objects.widget import WidgetResult, WidgetSpec
from shared.domain.value_objects.query_result import QueryResult


class TestWidgetSpec:
    def test_carries_id_title_sub_question_and_role(self) -> None:
        spec = WidgetSpec(
            id="widget-0",
            title="Revenue by month",
            sub_question="monthly revenue",
            role="analysis",
        )
        assert spec.id == "widget-0"
        assert spec.title == "Revenue by month"
        assert spec.sub_question == "monthly revenue"
        assert spec.role == "analysis"

    def test_carries_metric_role(self) -> None:
        spec = WidgetSpec(id="widget-0", title="Total", sub_question="total", role="metric")
        assert spec.role == "metric"

    def test_view_hint_defaults_to_none(self) -> None:
        # No explicit presentation requested → the view author chooses by data shape.
        spec = WidgetSpec(id="widget-0", title="t", sub_question="q", role="analysis")
        assert spec.view_hint is None

    def test_carries_explicit_view_hint(self) -> None:
        spec = WidgetSpec(
            id="widget-0", title="t", sub_question="q", role="analysis", view_hint="table"
        )
        assert spec.view_hint == "table"

    def test_is_frozen(self) -> None:
        spec = WidgetSpec(id="widget-0", title="t", sub_question="q", role="analysis")
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.id = "widget-1"  # type: ignore[misc]


class TestWidgetResult:
    def test_bundles_id_title_result_and_sql(self) -> None:
        result = QueryResult(columns=["n"], rows=[(42,)], row_count=1)
        widget = WidgetResult(widget_id="widget-0", title="Count", result=result, sql="SELECT 1")
        assert widget.widget_id == "widget-0"
        assert widget.title == "Count"
        assert widget.result is result
        assert widget.sql == "SELECT 1"

    def test_is_frozen(self) -> None:
        result = QueryResult(columns=["n"], rows=[(1,)], row_count=1)
        widget = WidgetResult(widget_id="w", title="t", result=result, sql="SELECT 1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            widget.sql = "SELECT 2"  # type: ignore[misc]
