from typing import cast

import pytest

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.view_spec import ChartSpec, KpiSpec, ViewSpec
from chat.infrastructure.eval.checks import (
    ExecutionMatchCheck,
    ResponseIncludesCheck,
    ResultSetCheck,
    RubricCheck,
    SqlValidCheck,
    ViewContainsCheck,
    ViewIntegrityCheck,
    deserialize_check,
)
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine

_GOLD_SQL = "SELECT COUNT(*) FROM movies WHERE Distributor = 'Warner Bros.'"


def _engine(gold: QueryResult) -> FakeSqlEngine:
    return FakeSqlEngine(results_by_sql={_GOLD_SQL: gold})


def _state_with_result(result: QueryResult) -> ChatState:
    return cast(ChatState, {"question": "How many films?", "query_result": result})


class TestExecutionMatchCheckScalar:
    def test_passes_when_candidate_matches_gold(self) -> None:
        # arrange — gold and candidate both return 318
        gold = QueryResult(columns=["c"], rows=[(318,)], row_count=1)
        candidate = QueryResult(columns=["count"], rows=[(318,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act
        result = check.evaluate(_state_with_result(candidate))
        # assert
        assert result["passed"] is True

    def test_fails_when_values_differ(self) -> None:
        # arrange
        gold = QueryResult(columns=["c"], rows=[(318,)], row_count=1)
        candidate = QueryResult(columns=["count"], rows=[(999,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act
        result = check.evaluate(_state_with_result(candidate))
        # assert
        assert result["passed"] is False

    def test_tolerates_float_precision(self) -> None:
        # arrange — gold rounds, candidate is unrounded
        gold = QueryResult(columns=["avg"], rows=[(6.77,)], row_count=1)
        candidate = QueryResult(columns=["avg"], rows=[(6.7741,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act
        result = check.evaluate(_state_with_result(candidate))
        # assert
        assert result["passed"] is True

    def test_tolerates_summation_noise_on_unrounded_large_floats(self) -> None:
        # arrange — two executions of a large SUM differ in the lowest digits
        gold = QueryResult(columns=["s"], rows=[(145047454.13116914,)], row_count=1)
        candidate = QueryResult(columns=["s"], rows=[(145047454.13116920,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act / assert
        assert check.evaluate(_state_with_result(candidate))["passed"] is True

    def test_rejects_fraction_vs_percentage(self) -> None:
        # arrange — a 100x unit error must still fail (0.0063 fraction vs 0.63 percent)
        gold = QueryResult(columns=["pct"], rows=[(0.63,)], row_count=1)
        candidate = QueryResult(columns=["pct"], rows=[(0.0063,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act / assert
        assert check.evaluate(_state_with_result(candidate))["passed"] is False


class TestExecutionMatchCheckRowSets:
    def test_passes_order_insensitive(self) -> None:
        # arrange — same rows, different order
        gold = QueryResult(columns=["s"], rows=[("SP",), ("RJ",)], row_count=2)
        candidate = QueryResult(columns=["s"], rows=[("RJ",), ("SP",)], row_count=2)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act / assert
        assert check.evaluate(_state_with_result(candidate))["passed"] is True

    def test_fails_when_row_counts_differ(self) -> None:
        # arrange — candidate dumps the whole column; gold expects one row
        gold = QueryResult(columns=["s"], rows=[("SP",)], row_count=1)
        candidate = QueryResult(columns=["s"], rows=[("SP",), ("RJ",), ("MG",)], row_count=3)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act / assert
        assert check.evaluate(_state_with_result(candidate))["passed"] is False

    def test_passes_when_candidate_has_extra_descriptive_column(self) -> None:
        # arrange — gold names the state; candidate also returns the count
        gold = QueryResult(columns=["state"], rows=[("SP",)], row_count=1)
        candidate = QueryResult(columns=["state", "n"], rows=[("SP", 11000)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act / assert — every gold value is present in the candidate row
        assert check.evaluate(_state_with_result(candidate))["passed"] is True


class TestSqlValidCheck:
    def test_passes_when_query_result_present(self) -> None:
        # kills mutmut_7 (bool(None) always False) and mutmut_10 (wrong key "QUERY_RESULT")
        result_val = QueryResult(columns=["c"], rows=[(1,)], row_count=1)
        state = cast(ChatState, {"query_result": result_val})
        result = SqlValidCheck().evaluate(state)
        assert result["passed"] is True

    def test_fails_when_query_result_absent(self) -> None:
        # kills mutmut_1 (state_dict=None → crash) and mutmut_3 (cast(dict, None) → crash)
        state = cast(ChatState, {})
        result = SqlValidCheck().evaluate(state)
        assert result["passed"] is False

    def test_type_key_is_sql_valid(self) -> None:
        # kills mutmut_13/14 (type="XXsql_validXX" or "SQL_VALID")
        state = cast(ChatState, {})
        result = SqlValidCheck().evaluate(state)
        assert result["type"] == "sql_valid"

    def test_value_is_empty_string(self) -> None:
        # kills mutmut_12 (value=None), mutmut_16 (value missing), mutmut_21 (value="XXXX")
        state = cast(ChatState, {})
        result = SqlValidCheck().evaluate(state)
        assert result["value"] == ""

    def test_reasoning_is_empty_string(self) -> None:
        # kills mutmut_14 (reasoning=None), mutmut_18 (missing), mutmut_22 (reasoning="XXXX")
        state = cast(ChatState, {})
        result = SqlValidCheck().evaluate(state)
        assert result["reasoning"] == ""


class TestExecutionMatchCheckMissingResult:
    def test_fails_without_query_result(self) -> None:
        # arrange
        gold = QueryResult(columns=["c"], rows=[(1,)], row_count=1)
        check = ExecutionMatchCheck(_GOLD_SQL, _engine(gold))
        # act
        result = check.evaluate(cast(ChatState, {"question": "q"}))
        # assert
        assert result["passed"] is False
        assert "no query result" in result["reasoning"]


class TestDeserializeExecutionMatch:
    def test_builds_execution_match_check_with_engine(self) -> None:
        # arrange
        engine = FakeSqlEngine()
        judge = FakeStructuredChatModel(passed=True, reasoning="")
        spec = {"type": "execution_match", "gold_sql": _GOLD_SQL}
        # act
        check = deserialize_check(spec, judge, engine)
        # assert — mutmut_47 passes engine=None; verify the correct engine is passed
        assert isinstance(check, ExecutionMatchCheck)
        assert check.gold_sql == _GOLD_SQL
        assert check.engine is engine

    def test_unknown_type_error_lists_all_valid_type_names(self) -> None:
        # arrange — error message must list all valid types by their exact lowercase names
        spec = {"type": "bad_type"}
        # act / assert — mutmut_10-19 corrupt the valid tuple; checking exact names kills them
        with pytest.raises(ValueError) as exc_info:
            deserialize_check(
                spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
            )
        err = str(exc_info.value)
        for name in (
            "response_includes",
            "sql_valid",
            "result_set",
            "execution_match",
            "rubric",
            "view_integrity",
            "view_contains",
        ):
            assert name in err, f"Expected {name!r} in error: {err}"
        # kills mutmut_10-18: "XXresponse_includesXX" is NOT the same as "response_includes"
        assert "XX" not in err

    def test_missing_type_defaults_to_empty_string_in_error(self) -> None:
        # kills mutmut_3 (default=None), mutmut_5 (no default), mutmut_8 (default="XXXX")
        with pytest.raises(ValueError) as exc_info:
            deserialize_check(
                {}, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
            )
        err = str(exc_info.value)
        # default must be "" so error says type=''; not None, not XXXX
        assert "None" not in err
        assert "''" in err


class TestRubricCheckEvaluate:
    """Calling evaluate() verifies that _chain is properly wired (not None)."""

    def test_evaluate_invokes_chain_and_returns_verdict(self) -> None:
        # arrange — mutmut_2 sets _chain=None, causing AttributeError on invoke
        model = FakeStructuredChatModel(passed=True, reasoning="Cites an exact number")
        check = RubricCheck(model, rubric="Must cite an exact number.")
        state = cast(ChatState, {"question": "Revenue?", "response": "Revenue is 42."})
        # act — calls self._chain.invoke(); fails if _chain is None
        result = check.evaluate(state)
        # assert
        assert result["passed"] is True
        assert result["type"] == "rubric"
        assert result["value"] == "Must cite an exact number."

    def test_evaluate_includes_question_response_rubric_in_prompt(self) -> None:
        # arrange — checks all three inputs reach the model's human message
        model = FakeStructuredChatModel(passed=True, reasoning="")
        check = RubricCheck(model, rubric="Must cite an exact number.")
        state = cast(ChatState, {"question": "Revenue?", "response": "Revenue is 42."})
        # act
        check.evaluate(state)
        # assert — kills mutmut_7 (question=None), mutmut_8 (response=None), mutmut_9 (rubric=None)
        # and mutmut_13/15/17 (wrong question key) and mutmut_20/24 (wrong response key)
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "Revenue?" in combined
        assert "Revenue is 42." in combined
        assert "Must cite an exact number." in combined

    def test_evaluate_returns_reasoning_from_verdict(self) -> None:
        # arrange — model returns specific reasoning; check it flows through
        model = FakeStructuredChatModel(passed=False, reasoning="Missing a specific number")
        check = RubricCheck(model, rubric="Must cite a number.")
        state = cast(ChatState, {"question": "q", "response": "No number here"})
        # act
        result = check.evaluate(state)
        # assert — kills mutmut_34 (reasoning=None) and mutmut_38 (reasoning omitted)
        assert result["reasoning"] == "Missing a specific number"
        assert result["passed"] is False

    def test_evaluate_uses_empty_string_when_question_missing_from_state(self) -> None:
        # arrange — state has no "question" key; default must be ""
        model = FakeStructuredChatModel(passed=True, reasoning="")
        check = RubricCheck(model, rubric="Must state revenue.")
        state = cast(ChatState, {"response": "Revenue is 42."})  # no "question" key
        # act
        check.evaluate(state)
        # assert — mutmut_19 uses "XXXX"; mutmut_14/16 use None; correct code uses ""
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "XXXX" not in combined
        assert "Question: None" not in combined  # kills mutmut_14 (default=None), mutmut_16

    def test_evaluate_uses_empty_string_when_response_missing_from_state(self) -> None:
        # arrange — state has no "response" key; default must be ""
        model = FakeStructuredChatModel(passed=True, reasoning="")
        check = RubricCheck(model, rubric="Must state revenue.")
        state = cast(ChatState, {"question": "Revenue?"})  # no "response" key
        # act
        check.evaluate(state)
        # assert — mutmut_26 uses "XXXX"; mutmut_21/23 use None; correct code uses ""
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "XXXX" not in combined
        assert "Response: None" not in combined  # kills mutmut_21 (default=None), mutmut_23


class TestDeserializeAllCheckTypes:
    def test_builds_response_includes_check(self) -> None:
        # arrange
        spec = {"type": "response_includes", "value": "42"}
        # act
        check = deserialize_check(
            spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
        )
        # assert
        assert isinstance(check, ResponseIncludesCheck)
        assert check.value == "42"

    def test_builds_sql_valid_check(self) -> None:
        # arrange
        spec: dict[str, str] = {"type": "sql_valid"}
        # act
        check = deserialize_check(
            spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
        )
        # assert
        assert isinstance(check, SqlValidCheck)

    def test_builds_result_set_check_without_column(self) -> None:
        # arrange
        spec = {"type": "result_set", "expected_value": "3201"}
        # act
        check = deserialize_check(
            spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
        )
        # assert
        assert isinstance(check, ResultSetCheck)
        assert check.expected_value == "3201"
        assert check.column is None

    def test_builds_result_set_check_with_column(self) -> None:
        # arrange
        spec = {"type": "result_set", "expected_value": "3201", "column": "total"}
        # act
        check = deserialize_check(
            spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
        )
        # assert
        assert isinstance(check, ResultSetCheck)
        assert check.column == "total"

    def test_builds_rubric_check(self) -> None:
        # arrange
        spec = {"type": "rubric", "rubric": "Must cite an exact number."}
        # act
        check = deserialize_check(
            spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
        )
        # assert
        assert isinstance(check, RubricCheck)
        assert check.rubric == "Must cite an exact number."

    def test_builds_view_integrity_check(self) -> None:
        # arrange
        spec: dict[str, str] = {"type": "view_integrity"}
        # act
        check = deserialize_check(
            spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
        )
        # assert
        assert isinstance(check, ViewIntegrityCheck)

    def test_builds_view_contains_check(self) -> None:
        # arrange
        spec = {"type": "view_contains", "element_type": "ChartJs"}
        # act
        check = deserialize_check(
            spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
        )
        # assert
        assert isinstance(check, ViewContainsCheck)
        assert check.element_type == "ChartJs"

    def test_unknown_type_raises_value_error(self) -> None:
        # arrange
        spec = {"type": "nonexistent_type"}
        # act / assert
        with pytest.raises(ValueError, match="nonexistent_type"):
            deserialize_check(
                spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
            )

    def test_missing_type_key_raises_value_error(self) -> None:
        # arrange — spec has no "type" key; default "" is not a valid type
        spec: dict[str, str] = {}
        # act / assert
        with pytest.raises(ValueError):
            deserialize_check(
                spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
            )


def _state_with_view(view_spec: ViewSpec, query_result: QueryResult) -> ChatState:
    return cast(
        ChatState,
        {"question": "Revenue by month", "query_result": query_result, "view_spec": view_spec},
    )


class TestViewIntegrityCheck:
    """ViewIntegrityCheck guards against the LLM recommending columns the result lacks."""

    def test_passes_when_all_referenced_columns_exist(self) -> None:
        # arrange — chart and KPI reference only real columns
        query_result = QueryResult(columns=["month", "revenue"], rows=[("Jan", 10)], row_count=1)
        spec = ViewSpec(
            kpis=[KpiSpec(label="Revenue", value_column="revenue")],
            charts=[
                ChartSpec(
                    kind="bar", title="Revenue", label_column="month", value_columns=["revenue"]
                )
            ],
            show_table=False,
        )
        # act
        result = ViewIntegrityCheck().evaluate(_state_with_view(spec, query_result))
        # assert
        assert result["passed"] is True
        assert result["type"] == "view_integrity"

    def test_fails_and_names_missing_chart_column(self) -> None:
        # arrange — chart references a column absent from the result
        query_result = QueryResult(columns=["month", "revenue"], rows=[("Jan", 10)], row_count=1)
        spec = ViewSpec(
            kpis=[],
            charts=[
                ChartSpec(kind="bar", title="x", label_column="month", value_columns=["profit"])
            ],
            show_table=False,
        )
        # act
        result = ViewIntegrityCheck().evaluate(_state_with_view(spec, query_result))
        # assert
        assert result["passed"] is False
        assert "profit" in result["reasoning"]

    def test_fails_when_kpi_column_missing(self) -> None:
        # arrange — KPI references a hallucinated column
        query_result = QueryResult(columns=["month", "revenue"], rows=[("Jan", 10)], row_count=1)
        spec = ViewSpec(
            kpis=[KpiSpec(label="Total", value_column="grand_total")],
            charts=[],
            show_table=False,
        )
        # act
        result = ViewIntegrityCheck().evaluate(_state_with_view(spec, query_result))
        # assert
        assert result["passed"] is False
        assert "grand_total" in result["reasoning"]

    def test_passes_vacuously_when_no_view_spec(self) -> None:
        # arrange — SQL-failure / narrative-only path: nothing to validate
        state = cast(ChatState, {"question": "q"})
        # act
        result = ViewIntegrityCheck().evaluate(state)
        # assert
        assert result["passed"] is True


class TestViewContainsCheck:
    """ViewContainsCheck asserts the assembled tree carries the expected element type."""

    def test_passes_when_element_type_present(self) -> None:
        # arrange — tree holds a ChartJs element
        view = RenderTree(
            root="root",
            elements={
                "root": RenderElement(type="Stack", props={}, children=["c"]),
                "c": RenderElement(type="ChartJs", props={}, children=[]),
            },
        )
        state = cast(ChatState, {"view": view})
        # act
        result = ViewContainsCheck(element_type="ChartJs").evaluate(state)
        # assert
        assert result["passed"] is True
        assert result["value"] == "ChartJs"

    def test_fails_when_element_type_absent(self) -> None:
        # arrange — narrative-only tree has no ChartJs
        view = RenderTree(
            root="root",
            elements={"root": RenderElement(type="Markdown", props={"text": "hi"}, children=[])},
        )
        state = cast(ChatState, {"view": view})
        # act
        result = ViewContainsCheck(element_type="ChartJs").evaluate(state)
        # assert
        assert result["passed"] is False
        assert "ChartJs" in result["reasoning"]

    def test_fails_when_no_view_present(self) -> None:
        # arrange — no view in state at all
        state = cast(ChatState, {"question": "q"})
        # act
        result = ViewContainsCheck(element_type="KpiStat").evaluate(state)
        # assert
        assert result["passed"] is False
