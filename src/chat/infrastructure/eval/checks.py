"""Correctness checks for text-to-SQL evaluation."""

from dataclasses import dataclass, field
from typing import Protocol, TypedDict, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.view_spec import ViewSpec
from chat.infrastructure.eval._result_matching import result_sets_match, value_matches
from shared.application.ports.sql_engine_port import SqlEnginePort
from shared.domain.value_objects.query_result import QueryResult


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
        """Return passed when query_result is present in state."""
        state_dict = cast(dict[str, object], state)
        passed = bool(state_dict.get("query_result"))
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
        """Return passed when any result cell matches expected_value."""
        state_dict = cast(dict[str, object], state)
        qr = state_dict.get("query_result")
        if not isinstance(qr, QueryResult):
            return CheckResult(
                type="result_set",
                value=self.expected_value,
                passed=False,
                reasoning="no query result",
            )
        rows = qr.to_dict_list()
        if self.column is not None:
            cells: list[object] = [row.get(self.column) for row in rows]
        else:
            cells = [v for row in rows for v in row.values()]
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
        """Return passed when candidate result matches gold_sql result."""
        candidate = cast(dict[str, object], state).get("query_result")
        if not isinstance(candidate, QueryResult):
            return CheckResult(
                type="execution_match",
                value=self.gold_sql,
                passed=False,
                reasoning="no query result",
            )
        gold = self.engine.execute_query(self.gold_sql)
        passed = result_sets_match(candidate, gold, self.order_matters)
        reasoning = (
            "" if passed else f"expected {gold.row_count} gold row(s), got {candidate.row_count}"
        )
        return CheckResult(
            type="execution_match",
            value=self.gold_sql,
            passed=passed,
            reasoning=reasoning,
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


def _referenced_columns(view_spec: ViewSpec) -> list[str]:
    """Collect every result column the ViewSpec references across its KPIs and charts."""
    columns = [kpi.value_column for kpi in view_spec.kpis]
    for chart in view_spec.charts:
        columns.append(chart.label_column)
        columns.extend(chart.value_columns)
    return columns


class ViewIntegrityCheck:
    """Passes when every column the recommend_view ViewSpec references exists in the result.

    Guards the generative-UI path: assemble_view silently drops KPIs/charts that name a
    missing column, so a hallucinated column would degrade the view without failing any
    SQL/narrative check. This asserts "no invented columns" — it passes vacuously when there
    is no view_spec (the SQL-failure / narrative-only path), so it never penalises the
    legitimate single-row KPI or null-label drop rules in render_tree_builder.

    Example:
        check = ViewIntegrityCheck()
        result = check.evaluate(state)  # {"type": "view_integrity", "passed": True, ...}
    """

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when no ViewSpec column is absent from the query result."""
        data = cast(dict[str, object], state)
        view_spec = data.get("view_spec")
        query_result = data.get("query_result")
        if not isinstance(view_spec, ViewSpec) or not isinstance(query_result, QueryResult):
            return CheckResult(type="view_integrity", value="", passed=True, reasoning="")
        missing = [c for c in _referenced_columns(view_spec) if c not in query_result.columns]
        reasoning = "" if not missing else f"columns not in result: {missing}"
        return CheckResult(type="view_integrity", value="", passed=not missing, reasoning=reasoning)


@dataclass
class ViewContainsCheck:
    """Passes when the assembled render tree contains at least one element of element_type.

    Asserts the LLM chose the right presentation for a question — e.g. a multi-row
    category result should yield a "ChartJs" element, a single headline metric a "KpiStat".

    Example:
        check = ViewContainsCheck(element_type="ChartJs")
        result = check.evaluate(state)  # {"type": "view_contains", "passed": True, ...}
    """

    element_type: str

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when any element in state["view"] has type == element_type."""
        view = cast(dict[str, object], state).get("view")
        passed = isinstance(view, RenderTree) and any(
            element.type == self.element_type for element in view.elements.values()
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
        case "view_contains":
            return ViewContainsCheck(element_type=spec["element_type"])
        case _:
            raise ValueError(f"Unknown check type {check_type!r}; expected one of {valid}")
