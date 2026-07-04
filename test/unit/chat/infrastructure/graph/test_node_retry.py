"""Tests for node-level RetryPolicy on the text2sql graph.

Transient errors (connection blips, 5xx) should be retried so a single flaky
call does not fail the whole run; deterministic bugs (ValueError) must surface
immediately rather than being retried.
"""

from types import SimpleNamespace

import pytest

from chat.infrastructure.graph.text2sql_graph import build_text2sql_graph
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.shared.infrastructure.sql_engine.flaky_sql_engine import FlakySqlEngine


def _make_model() -> FakeStructuredChatModel:
    """Model that drives the pipeline to a successful response."""
    return FakeStructuredChatModel(
        sql="SELECT 1",
        answer="One row.",
        tables=["orders"],
        widgets=[SimpleNamespace(title="Count", sub_question="how many")],
    )


def _make_engine(error: Exception, fail_times: int) -> FlakySqlEngine:
    """Flaky engine that fails list_tables ``fail_times`` before returning."""
    return FlakySqlEngine(
        tables=["orders"],
        schema="-- orders\nid INT",
        query_result=QueryResult(columns=["id"], rows=[(1,)], row_count=1),
        error=error,
        fail_times=fail_times,
    )


class TestNodeRetryPolicy:
    """Nodes are wired with a RetryPolicy that recovers from transient errors."""

    def test_transient_error_is_retried_and_recovers(self) -> None:
        """A single ConnectionError on list_tables is retried, then the run succeeds."""
        # arrange — first call raises a transient error, second succeeds
        engine = _make_engine(ConnectionError("temporary network blip"), fail_times=1)
        graph = build_text2sql_graph(_make_model(), engine)
        # act
        result = graph.invoke({"question": "How many?", "history": []})  # pyright: ignore[reportUnknownMemberType]
        # assert — retry fired (two calls) and the pipeline completed
        assert engine.list_tables_calls == 2
        assert result["narrative"] == "One row."

    def test_value_error_is_not_retried(self) -> None:
        """A ValueError surfaces on the first attempt (genuine bug, not transient)."""
        # arrange — list_tables always raises a non-transient error
        engine = _make_engine(ValueError("schema misconfigured"), fail_times=99)
        graph = build_text2sql_graph(_make_model(), engine)
        # act / assert — error propagates without a retry
        with pytest.raises(ValueError):
            graph.invoke({"question": "How many?", "history": []})  # pyright: ignore[reportUnknownMemberType]
        assert engine.list_tables_calls == 1
