"""Shared primitives for correctness checks: result type, protocol, and state accessors.

The result type, the ``Check`` protocol, and the ``ChatState`` accessors both ``checks``
and ``view_checks`` build on. Extracted so the data/SQL checks and the generative-UI view
checks can share ``CheckResult`` and the state accessors without an import cycle
(``deserialize_check`` in ``checks`` imports the view checks).
"""

from typing import Protocol, TypedDict, cast

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.widget import WidgetResult
from shared.domain.value_objects.query_result import QueryResult

# The component types the frontend json-render catalogue renders (frontend/src/catalog.ts).
# Single source both the view checks and the wire-integrity check validate element types
# against, so "in-catalog" means the same thing everywhere.
CATALOG_COMPONENTS = frozenset(
    {"Stack", "KpiRow", "Grid", "WidgetFrame", "Markdown", "KpiStat", "ChartJs", "DataTable"}
)


class CheckResult(TypedDict):
    """Outcome of a single correctness check; serialises directly to JSON."""

    type: str
    value: str  # rubric text for RubricCheck; empty string for SqlValidCheck
    passed: bool
    reasoning: str  # LLM explanation for RubricCheck; empty string for deterministic checks


class Check(Protocol):
    """Correctness check evaluated against a completed ChatState.

    OCP: add new check types by writing a new class — runner.py never changes.

    Example:
        check: Check = ResponseIncludesCheck("42")
        result = check.evaluate(state)  # CheckResult
    """

    def evaluate(self, state: ChatState) -> CheckResult:
        """Evaluate the check against a completed graph state."""
        ...


def all_results(state: ChatState) -> list[QueryResult]:
    """Every widget's executed result (a dashboard answer may have several)."""
    return [widget.result for widget in widget_results(state)]


def first_result(state: ChatState) -> QueryResult | None:
    """The first widget's executed result, or None when no widget produced one."""
    results = all_results(state)
    return results[0] if results else None


def widget_results(state: ChatState) -> list[WidgetResult]:
    """Every widget that produced an executed result, in fan-in order."""
    raw = cast(dict[str, object], state).get("widget_results")
    items = cast(list[object], raw) if isinstance(raw, list) else []
    return [item for item in items if isinstance(item, WidgetResult)]


def view_lines(state: ChatState) -> list[str]:
    """Every widget's authored SpecStream patch line, aggregated."""
    raw = cast(dict[str, object], state).get("widget_views")
    items = cast(list[object], raw) if isinstance(raw, list) else []
    return [line for line in items if isinstance(line, str)]


def collect_cells(results: list[QueryResult], column: str | None) -> list[object]:
    """Flatten result rows into a list of cells, optionally restricted to one column."""
    rows = [row for qr in results for row in qr.to_dict_list()]
    if column is not None:
        return [row.get(column) for row in rows]
    return [v for row in rows for v in row.values()]
