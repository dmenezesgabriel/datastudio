"""Correctness checks for text-to-SQL evaluation."""

from dataclasses import dataclass, field
from typing import Protocol, TypedDict, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.eval._result_matching import result_sets_match, value_matches
from chat.infrastructure.graph.spec_patch import parse_patch
from shared.application.ports.sql_engine_port import SqlEnginePort
from shared.domain.value_objects.query_result import QueryResult


def _all_results(state: ChatState) -> list[QueryResult]:
    """Every widget's executed result (a dashboard answer may have several)."""
    raw = cast(dict[str, object], state).get("widget_results")
    items = cast(list[object], raw) if isinstance(raw, list) else []
    return [item.result for item in items if isinstance(item, WidgetResult)]


def _first_result(state: ChatState) -> QueryResult | None:
    """The first widget's executed result, or None when no widget produced one."""
    results = _all_results(state)
    return results[0] if results else None


def _view_lines(state: ChatState) -> list[str]:
    """Every widget's authored SpecStream patch line, aggregated."""
    raw = cast(dict[str, object], state).get("widget_views")
    items = cast(list[object], raw) if isinstance(raw, list) else []
    return [line for line in items if isinstance(line, str)]


def _collect_cells(results: list[QueryResult], column: str | None) -> list[object]:
    """Flatten result rows into a list of cells, optionally restricted to one column."""
    rows = [row for qr in results for row in qr.to_dict_list()]
    if column is not None:
        return [row.get(column) for row in rows]
    return [v for row in rows for v in row.values()]


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


@dataclass
class ResponseIncludesCheck:
    """Passes when state["response"] contains value (case-insensitive).

    Example:
        check = ResponseIncludesCheck("42")
        result = check.evaluate(state)  # {"type": "response_includes", "passed": True, ...}
    """

    value: str

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when response contains self.value (case-insensitive)."""
        response = cast(dict[str, object], state).get("response") or ""
        passed = self.value.lower() in str(response).lower()
        return CheckResult(type="response_includes", value=self.value, passed=passed, reasoning="")


class SqlValidCheck:
    """Passes when the SQL executed successfully (query_result is present).

    Example:
        check = SqlValidCheck()
        result = check.evaluate(state)  # {"type": "sql_valid", "passed": True, ...}
    """

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when a widget produced a result."""
        passed = _first_result(state) is not None
        return CheckResult(type="sql_valid", value="", passed=passed, reasoning="")


@dataclass
class ResultSetCheck:
    """Passes when any cell in the query result matches expected_value.

    If column is given, only that column is checked; otherwise every column in
    every row is searched. Comparison normalises to float for numeric values so
    that int/float representations (3201 vs "3201") compare equal.

    Example:
        check = ResultSetCheck(expected_value="3201")
        result = check.evaluate(state)
        # {"type": "result_set", "value": "3201", "passed": True, "reasoning": ""}

        # With explicit column (use when the SQL always aliases the column):
        check = ResultSetCheck(expected_value="3201", column="total")
    """

    expected_value: str
    column: str | None = field(default=None)

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when any cell in any widget's result matches expected_value."""
        results = _all_results(state)
        if not results:
            return CheckResult(
                type="result_set",
                value=self.expected_value,
                passed=False,
                reasoning="no query result",
            )
        cells = _collect_cells(results, self.column)
        passed = any(value_matches(cell, self.expected_value) for cell in cells)
        label = f"{self.column}={self.expected_value}" if self.column else self.expected_value
        return CheckResult(type="result_set", value=label, passed=passed, reasoning="")


@dataclass
class ExecutionMatchCheck:
    """Execution accuracy: the candidate result must match a gold query's result.

    The gold SQL is executed against the same engine at eval time (so it stays
    correct as the data changes — the BIRD/Spider standard, not a frozen value).
    Comparison is an order-insensitive row match with numeric tolerance; each
    gold row must be covered by a distinct candidate row that contains all the
    gold cell values, so a candidate may carry extra descriptive columns but
    cannot dump the whole table (row counts must be equal).

    Example:
        check = ExecutionMatchCheck("SELECT COUNT(*) FROM movies", engine)
        result = check.evaluate(state)
        # {"type": "execution_match", "passed": True, ...}
    """

    gold_sql: str
    engine: SqlEnginePort
    order_matters: bool = field(default=False)

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when ANY widget's result matches the gold result.

        A dashboard may answer one question with several widgets (e.g. a ranked
        breakdown chart plus a headline KPI); the answer is correct if any of them
        reproduces the gold query's result.
        """
        candidates = _all_results(state)
        if not candidates:
            return CheckResult(
                type="execution_match",
                value=self.gold_sql,
                passed=False,
                reasoning="no query result",
            )
        gold = self.engine.execute_query(self.gold_sql)
        passed = any(result_sets_match(c, gold, self.order_matters) for c in candidates)
        counts = ", ".join(str(c.row_count) for c in candidates)
        reasoning = (
            "" if passed else f"no widget matched {gold.row_count} gold row(s); got [{counts}]"
        )
        return CheckResult(
            type="execution_match", value=self.gold_sql, passed=passed, reasoning=reasoning
        )


_JUDGE_SYSTEM_PROMPT = (
    "You are an evaluation judge. Given a question, a system response, and a rubric, "
    "decide whether the response satisfies the rubric."
)

_JUDGE_HUMAN_TEMPLATE = "Question: {question}\n\nResponse: {response}\n\nRubric: {rubric}"


class _RubricVerdict(BaseModel):
    passed: bool
    reasoning: str


class RubricCheck:
    """LLM-as-judge check against a natural-language rubric.

    The judge model is injected at construction (DIP), so the runner never
    needs to know about it — the check is self-contained.

    Example:
        check = RubricCheck(chat_model, "Answer must state an exact number.")
        result = check.evaluate(state)
        # {"type": "rubric", "passed": True, "reasoning": "The response states 42..."}
    """

    def __init__(self, model: BaseChatModel, rubric: str) -> None:
        """Wire the judge chain; model and rubric are fixed for the lifetime of the check."""
        self.rubric = rubric
        self._chain: Runnable[LanguageModelInput, _RubricVerdict] = cast(
            Runnable[LanguageModelInput, _RubricVerdict],
            model.with_structured_output(_RubricVerdict),
        )

    def evaluate(self, state: ChatState) -> CheckResult:
        """Invoke the LLM judge and return its verdict as a CheckResult."""
        state_dict = cast(dict[str, object], state)
        human_content = _JUDGE_HUMAN_TEMPLATE.format(
            question=state_dict.get("question", ""),
            response=state_dict.get("response", ""),
            rubric=self.rubric,
        )
        verdict: _RubricVerdict = self._chain.invoke(
            [
                SystemMessage(content=_JUDGE_SYSTEM_PROMPT),
                HumanMessage(content=human_content),
            ]
        )
        return CheckResult(
            type="rubric",
            value=self.rubric,
            passed=verdict.passed,
            reasoning=verdict.reasoning,
        )


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
        view_lines = _view_lines(state)
        results = _all_results(state)
        if not view_lines or not results:
            return CheckResult(type="view_integrity", value="", passed=True, reasoning="")
        known = {column for qr in results for column in qr.columns}
        missing = [c for c in _referenced_columns(view_lines) if c not in known]
        reasoning = "" if not missing else f"columns not in result: {missing}"
        return CheckResult(type="view_integrity", value="", passed=not missing, reasoning=reasoning)


_VIEW_COMPONENTS = frozenset({"KpiStat", "ChartJs", "DataTable"})
_KNOWN_COMPONENTS = _VIEW_COMPONENTS | {"Markdown", "Stack"}


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
        view_lines = _view_lines(state)
        if not view_lines:
            return CheckResult(type="view_present", value="", passed=False, reasoning="no view")
        types = [element.get("type") for element in _added_elements(view_lines)]
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
    """Passes when the LLM-authored view emits at least one element of element_type.

    Asserts the model chose a fitting presentation — e.g. a multi-row category result
    should yield a "ChartJs" element. Since the view is now LLM-authored, this is a
    soft expectation rather than a guarantee.

    Example:
        check = ViewContainsCheck(element_type="ChartJs")
        result = check.evaluate(state)  # {"type": "view_contains", "passed": True, ...}
    """

    element_type: str

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when any element added by the view has type == element_type."""
        passed = any(
            element.get("type") == self.element_type
            for element in _added_elements(_view_lines(state))
        )
        reasoning = "" if passed else f"no {self.element_type} element in view"
        return CheckResult(
            type="view_contains", value=self.element_type, passed=passed, reasoning=reasoning
        )


def deserialize_check(
    spec: dict[str, str], judge_model: BaseChatModel, sql_engine: SqlEnginePort
) -> Check:
    """Build a Check from a JSON spec dict.

    Example:
        check = deserialize_check({"type": "sql_valid"}, model, engine)
        check = deserialize_check(
            {"type": "execution_match", "gold_sql": "SELECT 1"}, model, engine
        )
    """
    check_type = spec.get("type", "")
    valid = (
        "response_includes",
        "sql_valid",
        "result_set",
        "execution_match",
        "rubric",
        "view_integrity",
        "view_present",
        "view_contains",
    )
    match check_type:
        case "response_includes":
            return ResponseIncludesCheck(value=spec["value"])
        case "sql_valid":
            return SqlValidCheck()
        case "result_set":
            return ResultSetCheck(
                expected_value=spec["expected_value"],
                column=spec.get("column"),
            )
        case "execution_match":
            return ExecutionMatchCheck(gold_sql=spec["gold_sql"], engine=sql_engine)
        case "rubric":
            return RubricCheck(model=judge_model, rubric=spec["rubric"])
        case "view_integrity":
            return ViewIntegrityCheck()
        case "view_present":
            return ViewPresentCheck()
        case "view_contains":
            return ViewContainsCheck(element_type=spec["element_type"])
        case _:
            raise ValueError(f"Unknown check type {check_type!r}; expected one of {valid}")
