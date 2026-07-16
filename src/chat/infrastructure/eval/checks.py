"""Correctness checks for text-to-SQL evaluation.

Data/SQL/text checks live here; the generative-UI view checks live in ``view_checks``.
``deserialize_check`` is the single factory that maps a JSON spec to any check type.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.infrastructure.eval._check_base import (
    Check,
    CheckResult,
    all_results,
    collect_cells,
    first_result,
)
from chat.infrastructure.eval._result_matching import result_sets_match, value_matches
from chat.infrastructure.eval.edit_checks import (
    EditModeCheck,
    ElementRemovedCheck,
    WidgetKindCheck,
    WidgetsPreservedCheck,
)
from chat.infrastructure.eval.view_checks import (
    ChartFitCheck,
    KpiBandPopulatedCheck,
    TextAnswerCheck,
    ViewContainsCheck,
    ViewIntegrityCheck,
    ViewPresentCheck,
    VizRubricCheck,
    WidgetCountCheck,
)
from chat.infrastructure.eval.wire_integrity_check import WireIntegrityCheck
from chat.infrastructure.graph.chat_state import ChatState
from shared.application.ports.sql_engine_port import SqlEnginePort
from shared.domain.value_objects.query_result import QueryResult


@dataclass
class ResponseIncludesCheck:
    """Passes when state["narrative"] contains value (case-insensitive).

    Example:
        check = ResponseIncludesCheck("42")
        result = check.evaluate(state)  # {"type": "response_includes", "passed": True, ...}
    """

    value: str

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when response contains self.value (case-insensitive)."""
        response = cast(dict[str, object], state).get("narrative") or ""
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
        passed = first_result(state) is not None
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
        results = all_results(state)
        if not results:
            return CheckResult(
                type="result_set",
                value=self.expected_value,
                passed=False,
                reasoning="no query result",
            )
        cells = collect_cells(results, self.column)
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
        check = ExecutionMatchCheck("SELECT COUNT(*) FROM events", engine)
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
        candidates = all_results(state)
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


@dataclass
class ResultSetAnyCheck:
    """Passes when any cell matches ANY of the expected values (answer-set tolerance).

    The multi-gold sibling of ResultSetCheck for scalar answers hiding in a wider result
    (e.g. the final cumulative total under either of two defensible metric definitions),
    where full result-set matching would be brittle to axis formatting.

    Example:
        check = ResultSetAnyCheck(expected_value_options=["1000.5", "1180.2"])
        result = check.evaluate(state)  # {"type": "result_set_any", "passed": True, ...}
    """

    expected_value_options: list[str]
    column: str | None = field(default=None)

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when any cell in any widget's result matches any expected value."""
        label = " | ".join(self.expected_value_options)
        results = all_results(state)
        if not results:
            return CheckResult(
                type="result_set_any", value=label, passed=False, reasoning="no query result"
            )
        cells = collect_cells(results, self.column)
        passed = any(
            value_matches(cell, expected)
            for expected in self.expected_value_options
            for cell in cells
        )
        reasoning = "" if passed else "no cell matched any expected value"
        return CheckResult(type="result_set_any", value=label, passed=passed, reasoning=reasoning)


@dataclass
class ExecutionMatchAnyCheck:
    """Execution accuracy with answer-set tolerance: any of N gold queries may match.

    Real questions often admit several defensible metric definitions (revenue with or
    without freight, customers by id vs unique id, labels spelled differently). Each
    defensible reading gets its own gold query; the answer is correct when ANY widget's
    result matches ANY gold — so "different-but-valid" stops grading as "wrong" while
    the comparison itself stays as strict as ExecutionMatchCheck's.

    Example:
        check = ExecutionMatchAnyCheck(
            ["SELECT SUM(amount) FROM events", "SELECT SUM(amount + fee) FROM events"],
            engine,
        )
        result = check.evaluate(state)  # {"type": "execution_match_any", "passed": True, ...}
    """

    gold_sql_options: list[str]
    engine: SqlEnginePort

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when any widget's result matches any gold query's result."""
        label = f"{len(self.gold_sql_options)} gold options"
        candidates = all_results(state)
        if not candidates:
            return CheckResult(
                type="execution_match_any", value=label, passed=False, reasoning="no query result"
            )
        golds = [self.engine.execute_query(sql) for sql in self.gold_sql_options]
        passed = any(
            result_sets_match(candidate, gold, order_matters=False)
            for candidate in candidates
            for gold in golds
        )
        reasoning = "" if passed else self._miss_reasoning(candidates, golds)
        return CheckResult(
            type="execution_match_any", value=label, passed=passed, reasoning=reasoning
        )

    def _miss_reasoning(self, candidates: list[QueryResult], golds: list[QueryResult]) -> str:
        """Describe the miss: candidate row counts vs each gold's row count."""
        got = ", ".join(str(c.row_count) for c in candidates)
        wanted = ", ".join(str(g.row_count) for g in golds)
        return f"no widget matched any gold (gold row counts [{wanted}]); got [{got}]"


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
            response=state_dict.get("narrative", ""),
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
    # Dispatch table keeps this factory flat (one lookup) instead of a long match —
    # each builder is only invoked for its own type, so missing fields still raise.
    builders: dict[str, Callable[[], Check]] = {
        "response_includes": lambda: ResponseIncludesCheck(value=spec["value"]),
        "sql_valid": SqlValidCheck,
        "result_set": lambda: ResultSetCheck(
            expected_value=spec["expected_value"], column=spec.get("column")
        ),
        "execution_match": lambda: ExecutionMatchCheck(
            gold_sql=spec["gold_sql"],
            engine=sql_engine,
            order_matters=bool(spec.get("order_matters", False)),
        ),
        "execution_match_any": lambda: ExecutionMatchAnyCheck(
            gold_sql_options=list(cast(list[str], spec["gold_sql_options"])),
            engine=sql_engine,
        ),
        "result_set_any": lambda: ResultSetAnyCheck(
            expected_value_options=list(cast(list[str], spec["expected_value_options"])),
            column=spec.get("column"),
        ),
        "rubric": lambda: RubricCheck(model=judge_model, rubric=spec["rubric"]),
        "view_integrity": ViewIntegrityCheck,
        "view_present": ViewPresentCheck,
        "view_contains": lambda: ViewContainsCheck(
            element_type=spec["element_type"], chart_kind=spec.get("chart_kind")
        ),
        "chart_fit": ChartFitCheck,
        "kpi_band_populated": lambda: KpiBandPopulatedCheck(min_kpis=int(spec.get("min_kpis", 1))),
        "text_answer": TextAnswerCheck,
        "widget_count": lambda: WidgetCountCheck(min_widgets=int(spec["min_widgets"])),
        "viz_rubric": lambda: VizRubricCheck(model=judge_model, rubric=spec["rubric"]),
        "wire_integrity": WireIntegrityCheck,
        "edit_mode": lambda: EditModeCheck(expected_mode=spec["expected_mode"]),
        "widget_kind": lambda: WidgetKindCheck(
            widget_id=spec["widget_id"],
            element_type=spec["element_type"],
            chart_kind=spec.get("chart_kind"),
        ),
        "widgets_preserved": lambda: WidgetsPreservedCheck(
            widget_ids=cast(list[str], spec["widget_ids"])
        ),
        "element_removed": lambda: ElementRemovedCheck(element_id=spec["element_id"]),
    }
    check_type = spec.get("type", "")
    if check_type not in builders:
        raise ValueError(f"Unknown check type {check_type!r}; expected one of {tuple(builders)}")
    return builders[check_type]()
