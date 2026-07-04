"""Generative-UI view checks over the LLM-authored SpecStream.

Assert the model chose a fitting, in-vocabulary, best-practice visualization for the
question and data. These are separate from the data/SQL checks in ``checks`` because they
reason over the authored view (element types, chart ``kind``, and how those fit the result
shape) rather than over query results. ``deserialize_check`` wires them into the factory.
"""

import re
from dataclasses import dataclass
from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.eval._check_base import (
    CATALOG_COMPONENTS,
    CheckResult,
    all_results,
    view_lines,
    widget_results,
)
from chat.infrastructure.graph.spec_patch import parse_patch
from shared.domain.value_objects.query_result import QueryResult

# A pie stops being readable past a handful of slices (data-to-viz anti-pattern); beyond
# this, bar or table is the right call. KpiStat is single-row only per the catalog.
_MAX_PIE_SLICES = 5
_PIE_KIND = "pie"
_WIDGET_ID_RE = re.compile(r"^(widget-\d+)")


def _added_elements(view_lines: list[str]) -> list[dict[str, object]]:
    """Parse the LLM-authored SpecStream lines into the element value dicts they add."""
    elements: list[dict[str, object]] = []
    for line in view_lines:
        patch = parse_patch(line)
        value = patch.get("value") if patch is not None else None
        if isinstance(value, dict) and "type" in value:
            elements.append(cast(dict[str, object], value))
    return elements


def _referenced_columns(view_lines: list[str]) -> list[str]:
    """Collect every result column the LLM-authored view binds to (by name)."""
    columns: list[str] = []
    for element in _added_elements(view_lines):
        props = element.get("props")
        if not isinstance(props, dict):
            continue
        typed_props = cast(dict[str, object], props)
        for key in ("labelColumn", "valueColumn"):
            name = typed_props.get(key)
            if isinstance(name, str):
                columns.append(name)
        value_columns = typed_props.get("valueColumns")
        if isinstance(value_columns, list):
            columns.extend(c for c in cast(list[object], value_columns) if isinstance(c, str))
    return columns


class ViewIntegrityCheck:
    """Passes when every column the LLM-authored view references exists in the result.

    Guards the generative-UI path: the model authors the visualization, so a hallucinated
    column would bind a chart/KPI to data that isn't there. This asserts "no invented
    columns" — it passes vacuously when there are no view_lines (the SQL-failure /
    narrative-only path), so it never penalises a legitimately minimal view.

    Example:
        check = ViewIntegrityCheck()
        result = check.evaluate(state)  # {"type": "view_integrity", "passed": True, ...}
    """

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when no column any widget binds to is absent from every result."""
        lines = view_lines(state)
        results = all_results(state)
        if not lines or not results:
            return CheckResult(type="view_integrity", value="", passed=True, reasoning="")
        known = {column for qr in results for column in qr.columns}
        missing = [c for c in _referenced_columns(lines) if c not in known]
        reasoning = "" if not missing else f"columns not in result: {missing}"
        return CheckResult(type="view_integrity", value="", passed=not missing, reasoning=reasoning)


_VIEW_COMPONENTS = frozenset({"KpiStat", "ChartJs", "DataTable"})
_KNOWN_COMPONENTS = CATALOG_COMPONENTS


class ViewPresentCheck:
    """Passes when the LLM-authored view adds an in-vocabulary visualization element.

    Deterministic structural guard for the generative-UI path: asserts the model produced a
    renderable view (chart/KPI/table) using only known catalogue components — without pinning
    the exact element type, which is now the model's choice (use ViewContainsCheck for that).

    Example:
        check = ViewPresentCheck()
        result = check.evaluate(state)  # {"type": "view_present", "passed": True, ...}
    """

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when ≥1 known viz element is added and no unknown component appears."""
        lines = view_lines(state)
        if not lines:
            return CheckResult(type="view_present", value="", passed=False, reasoning="no view")
        types = [element.get("type") for element in _added_elements(lines)]
        unknown = [t for t in types if t not in _KNOWN_COMPONENTS]
        if unknown:
            return CheckResult(
                type="view_present",
                value="",
                passed=False,
                reasoning=f"unknown components: {unknown}",
            )
        has_viz = any(t in _VIEW_COMPONENTS for t in types)
        reasoning = "" if has_viz else "no visualization element"
        return CheckResult(type="view_present", value="", passed=has_viz, reasoning=reasoning)


@dataclass
class ViewContainsCheck:
    """Passes when the view emits an element of element_type (optionally a ChartJs kind).

    Asserts the model chose a fitting presentation — e.g. a scalar answer should yield a
    "KpiStat", a time series a "ChartJs" of kind "line". When chart_kind is set, an element
    must be a ChartJs whose props.kind equals it. Since the view is LLM-authored, this is a
    soft expectation rather than a guarantee.

    Example:
        check = ViewContainsCheck(element_type="ChartJs", chart_kind="line")
        result = check.evaluate(state)  # {"type": "view_contains", "passed": True, ...}
    """

    element_type: str
    chart_kind: str | None = None

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when an added element matches element_type (and chart_kind if set)."""
        elements = _added_elements(view_lines(state))
        passed = any(self._matches(element) for element in elements)
        label = (
            self.element_type
            if self.chart_kind is None
            else f"{self.element_type}:{self.chart_kind}"
        )
        reasoning = "" if passed else f"no {label} element in view"
        return CheckResult(type="view_contains", value=label, passed=passed, reasoning=reasoning)

    def _matches(self, element: dict[str, object]) -> bool:
        """True when the element is the expected type and, if required, the expected chart kind."""
        if element.get("type") != self.element_type:
            return False
        if self.chart_kind is None:
            return True
        return _chart_kind(element) == self.chart_kind


def _chart_kind(element: dict[str, object]) -> str | None:
    """The ChartJs ``kind`` prop, or None when the element is not a kinded chart."""
    props = element.get("props")
    if not isinstance(props, dict):
        return None
    kind = cast(dict[str, object], props).get("kind")
    return kind if isinstance(kind, str) else None


def _row_count_for(element_id: str, results_by_widget: dict[str, QueryResult]) -> int | None:
    """Row count of the result the element belongs to (matched by its widget-id prefix)."""
    match = _WIDGET_ID_RE.match(element_id)
    if match is None:
        # Un-namespaced id (e.g. in a unit test): fall back to the sole result if unambiguous.
        return (
            next(iter(results_by_widget.values())).row_count
            if len(results_by_widget) == 1
            else None
        )
    result = results_by_widget.get(match.group(1))
    return result.row_count if result is not None else None


class ChartFitCheck:
    """Passes when no chart/KPI element violates a data-shape best practice.

    Deterministic anti-pattern guard on the LLM-authored view (data-to-viz rules):
    - a pie chart bound to more than five categories is unreadable → use bar/table;
    - a KpiStat must summarise a single row, never a multi-row result.

    Passes vacuously when there is no view or no result, so it never faults the
    SQL-failure / narrative-only path.

    Example:
        check = ChartFitCheck()
        result = check.evaluate(state)  # {"type": "chart_fit", "passed": True, ...}
    """

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when every pie has ≤5 slices and every KPI summarises one row."""
        results_by_widget = {w.widget_id: w.result for w in widget_results(state)}
        if not results_by_widget:
            return CheckResult(type="chart_fit", value="", passed=True, reasoning="")
        violations = self._violations(view_lines(state), results_by_widget)
        reasoning = "; ".join(violations)
        return CheckResult(type="chart_fit", value="", passed=not violations, reasoning=reasoning)

    def _violations(
        self, view_lines: list[str], results_by_widget: dict[str, QueryResult]
    ) -> list[str]:
        """Collect a message per element that breaks a data-shape best practice."""
        violations: list[str] = []
        for line in view_lines:
            patch = parse_patch(line)
            element = patch.get("value") if patch is not None else None
            if not isinstance(element, dict) or "type" not in element:
                continue
            path = str(patch.get("path", "")) if patch is not None else ""
            element_id = path.removeprefix("/elements/")
            rows = _row_count_for(element_id, results_by_widget)
            fault = self._fault(cast(dict[str, object], element), rows)
            if fault is not None:
                violations.append(fault)
        return violations

    def _fault(self, element: dict[str, object], rows: int | None) -> str | None:
        """A best-practice violation message for one element, or None when it is fine."""
        if rows is None:
            return None
        kind = _chart_kind(element)
        if kind == _PIE_KIND and rows > _MAX_PIE_SLICES:
            return f"pie chart with {rows} slices (>{_MAX_PIE_SLICES}); use bar or table"
        if element.get("type") == "KpiStat" and rows > 1:
            return f"KpiStat bound to a {rows}-row result; KPI must be single-row"
        return None


@dataclass
class WidgetCountCheck:
    """Passes when the answer built at least ``min_widgets`` widgets.

    Asserts the dashboard branch fired: an "overview"/"dashboard" question should decompose
    into several widgets (a KPI headline, a trend chart, a breakdown), not a single answer.

    Example:
        check = WidgetCountCheck(min_widgets=2)
        result = check.evaluate(state)  # {"type": "widget_count", "passed": True, ...}
    """

    min_widgets: int

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when the number of built widgets is at least min_widgets."""
        count = len(widget_results(state))
        passed = count >= self.min_widgets
        reasoning = "" if passed else f"built {count} widget(s), expected ≥{self.min_widgets}"
        return CheckResult(
            type="widget_count", value=str(self.min_widgets), passed=passed, reasoning=reasoning
        )


class TextAnswerCheck:
    """Passes when the turn is a text-only answer: a non-empty response and no widgets.

    Asserts the planner routed a conversational/definitional/meta question to the text
    branch (answer_text) instead of forcing a SQL widget — the "just answer in words"
    response type.

    Example:
        check = TextAnswerCheck()
        result = check.evaluate(state)  # {"type": "text_answer", "passed": True, ...}
    """

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when a response is present and no widget was built."""
        results = widget_results(state)
        response = cast(dict[str, object], state).get("response")
        has_text = isinstance(response, str) and bool(response.strip())
        passed = has_text and not results
        if not has_text:
            reasoning = "no text response"
        elif results:
            reasoning = f"expected a text-only answer but built {len(results)} widget(s)"
        else:
            reasoning = ""
        return CheckResult(type="text_answer", value="", passed=passed, reasoning=reasoning)


_VIZ_JUDGE_SYSTEM_PROMPT = (
    "You are a data-visualization reviewer. Given a question, the chosen visualization "
    "elements, the shape of the underlying data, and a rubric, decide whether the "
    "presentation follows data-visualization best practices. Judge the CHOICE of view type "
    "(KPI vs chart vs table) and chart kind (bar/line/pie) against the data — not the text."
)

_VIZ_JUDGE_HUMAN_TEMPLATE = (
    "Question: {question}\n\nChosen views:\n{views}\n\nData shape:\n{data}\n\nRubric: {rubric}"
)


class _VizVerdict(BaseModel):
    passed: bool
    reasoning: str


def _describe_views(view_lines: list[str]) -> str:
    """One line per authored element: its type and, for a chart, its kind and columns."""
    lines: list[str] = []
    for element in _added_elements(view_lines):
        kind = _chart_kind(element)
        suffix = f" (kind={kind})" if kind is not None else ""
        lines.append(f"- {element.get('type')}{suffix}")
    return "\n".join(lines) or "- (none)"


def _describe_results(results: list[QueryResult]) -> str:
    """One line per widget result: its column names and row count."""
    lines = [f"- columns={qr.columns}, rows={qr.row_count}" for qr in results]
    return "\n".join(lines) or "- (none)"


class VizRubricCheck:
    """LLM-as-judge check on visualization appropriateness against a rubric.

    Unlike RubricCheck (which judges the text response), this feeds the judge the chosen
    view types, chart kinds, and the data shape, so a rubric can assert a defensible-but-
    ambiguous presentation choice (e.g. "a ranking is acceptable as either a bar chart or a
    table, but never a pie"). The judge model is injected (DIP).

    Example:
        check = VizRubricCheck(model, "A monthly trend should be a line chart.")
        result = check.evaluate(state)  # {"type": "viz_rubric", "passed": True, ...}
    """

    def __init__(self, model: BaseChatModel, rubric: str) -> None:
        """Wire the judge chain; model and rubric are fixed for the lifetime of the check."""
        self.rubric = rubric
        self._chain: Runnable[LanguageModelInput, _VizVerdict] = cast(
            Runnable[LanguageModelInput, _VizVerdict],
            model.with_structured_output(_VizVerdict),
        )

    def evaluate(self, state: ChatState) -> CheckResult:
        """Invoke the LLM judge over the chosen views + data shape and return its verdict."""
        state_dict = cast(dict[str, object], state)
        human_content = _VIZ_JUDGE_HUMAN_TEMPLATE.format(
            question=state_dict.get("question", ""),
            views=_describe_views(view_lines(state)),
            data=_describe_results(all_results(state)),
            rubric=self.rubric,
        )
        verdict: _VizVerdict = self._chain.invoke(
            [
                SystemMessage(content=_VIZ_JUDGE_SYSTEM_PROMPT),
                HumanMessage(content=human_content),
            ]
        )
        return CheckResult(
            type="viz_rubric", value=self.rubric, passed=verdict.passed, reasoning=verdict.reasoning
        )
