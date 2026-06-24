from dataclasses import dataclass, field
from typing import Protocol, TypedDict, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState
from shared.domain.value_objects.query_result import QueryResult


class CheckResult(TypedDict):
    """Outcome of a single correctness check; serialises directly to JSON."""

    type: str
    value: str  # rubric text for RubricCheck; empty string for SqlValidCheck
    passed: bool
    reasoning: (
        str  # LLM explanation for RubricCheck; empty string for deterministic checks
    )


class Check(Protocol):
    """Correctness check evaluated against a completed ChatState.

    OCP: add new check types by writing a new class — runner.py never changes.

    Example:
        check: Check = ResponseIncludesCheck("42")
        result = check.evaluate(state)  # CheckResult
    """

    def evaluate(self, state: ChatState) -> CheckResult: ...


@dataclass
class ResponseIncludesCheck:
    """Passes when state["response"] contains value (case-insensitive).

    Example:
        check = ResponseIncludesCheck("42")
        result = check.evaluate(state)  # {"type": "response_includes", "passed": True, ...}
    """

    value: str

    def evaluate(self, state: ChatState) -> CheckResult:
        response = cast(dict[str, object], state).get("response") or ""
        passed = self.value.lower() in str(response).lower()
        return CheckResult(
            type="response_includes", value=self.value, passed=passed, reasoning=""
        )


@dataclass
class SqlContainsCheck:
    """Passes when state["sql_query"] contains value (case-insensitive).

    Example:
        check = SqlContainsCheck("COUNT")
        result = check.evaluate(state)  # {"type": "sql_contains", "passed": True, ...}
    """

    value: str

    def evaluate(self, state: ChatState) -> CheckResult:
        sql = cast(dict[str, object], state).get("sql_query") or ""
        passed = self.value.lower() in str(sql).lower()
        return CheckResult(
            type="sql_contains", value=self.value, passed=passed, reasoning=""
        )


class SqlValidCheck:
    """Passes when the SQL executed successfully (query_result is present).

    Example:
        check = SqlValidCheck()
        result = check.evaluate(state)  # {"type": "sql_valid", "passed": True, ...}
    """

    def evaluate(self, state: ChatState) -> CheckResult:
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
        passed = any(_value_matches(cell, self.expected_value) for cell in cells)
        label = (
            f"{self.column}={self.expected_value}"
            if self.column
            else self.expected_value
        )
        return CheckResult(type="result_set", value=label, passed=passed, reasoning="")


def _value_matches(cell: object, expected: str) -> bool:
    """Compare a result cell to an expected string, normalising numeric types.

    Rounds to the precision implied by the expected string before comparing, so
    an unrounded AVG result (6.7741...) matches an expected value of "6.77".
    """
    try:
        cell_f = float(str(cell))
        exp_f = float(expected)
        decimals = len(expected.split(".")[1]) if "." in expected else 0
        return round(cell_f, decimals) == round(exp_f, decimals)
    except (ValueError, TypeError):
        return str(cell).strip().lower() == expected.strip().lower()


_JUDGE_SYSTEM_PROMPT = (
    "You are an evaluation judge. Given a question, a system response, and a rubric, "
    "decide whether the response satisfies the rubric."
)

_JUDGE_HUMAN_TEMPLATE = (
    "Question: {question}\n\nResponse: {response}\n\nRubric: {rubric}"
)


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
        self.rubric = rubric
        self._chain: Runnable[LanguageModelInput, _RubricVerdict] = cast(
            Runnable[LanguageModelInput, _RubricVerdict],
            model.with_structured_output(_RubricVerdict),
        )

    def evaluate(self, state: ChatState) -> CheckResult:
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


def deserialize_check(spec: dict[str, str], judge_model: BaseChatModel) -> Check:
    """Build a Check from a JSON spec dict.

    Example:
        check = deserialize_check({"type": "sql_valid"}, model)
        check = deserialize_check({"type": "rubric", "rubric": "Must be a sentence."}, model)
    """
    check_type = spec.get("type", "")
    valid = ("response_includes", "sql_contains", "sql_valid", "result_set", "rubric")
    match check_type:
        case "response_includes":
            return ResponseIncludesCheck(value=spec["value"])
        case "sql_contains":
            return SqlContainsCheck(value=spec["value"])
        case "sql_valid":
            return SqlValidCheck()
        case "result_set":
            return ResultSetCheck(
                expected_value=spec["expected_value"],
                column=spec.get("column"),
            )
        case "rubric":
            return RubricCheck(model=judge_model, rubric=spec["rubric"])
        case _:
            raise ValueError(
                f"Unknown check type {check_type!r}; expected one of {valid}"
            )
