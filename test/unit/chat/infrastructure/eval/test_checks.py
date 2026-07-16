import json
from typing import cast

import pytest

from chat.domain.value_objects.widget import WidgetResult
from chat.infrastructure.eval.checks import (
    ExecutionMatchAnyCheck,
    ExecutionMatchCheck,
    ResponseIncludesCheck,
    ResultSetAnyCheck,
    ResultSetCheck,
    RubricCheck,
    SqlValidCheck,
    ViewContainsCheck,
    ViewIntegrityCheck,
    ViewPresentCheck,
    deserialize_check,
)
from chat.infrastructure.graph.chat_state import ChatState
from shared.domain.value_objects.query_result import QueryResult
from test.unit.chat.infrastructure.graph.nodes.fake_structured_chat_model import (
    FakeStructuredChatModel,
)
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine

_GOLD_SQL = "SELECT COUNT(*) FROM movies WHERE Distributor = 'Warner Bros.'"


def _engine(gold: QueryResult) -> FakeSqlEngine:
    return FakeSqlEngine(results_by_sql={_GOLD_SQL: gold})


def _state_with_result(result: QueryResult) -> ChatState:
    widget = WidgetResult(widget_id="widget-0", title="Films", result=result, sql="SELECT 1")
    return cast(ChatState, {"question": "How many films?", "widget_results": [widget]})


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
    def test_passes_when_a_widget_result_is_present(self) -> None:
        # kills mutmut_7 (bool(None) always False)
        state = _state_with_result(QueryResult(columns=["c"], rows=[(1,)], row_count=1))
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


class TestResultSetCheckEvaluate:
    """ResultSetCheck scans widget result cells for an expected value."""

    def test_matches_any_cell_when_no_column_given(self) -> None:
        # arrange — the value appears in some column of some row
        result = QueryResult(columns=["state", "revenue"], rows=[("SP", 5202955.05)], row_count=1)
        # act / assert
        assert ResultSetCheck(expected_value="SP").evaluate(_state_with_result(result))["passed"]

    def test_matches_within_the_named_column(self) -> None:
        # arrange — restrict the search to one column
        result = QueryResult(columns=["state", "n"], rows=[("SP", 100)], row_count=1)
        # act
        result_check = ResultSetCheck(expected_value="100", column="n").evaluate(
            _state_with_result(result)
        )
        # assert
        assert result_check["passed"] is True
        assert result_check["value"] == "n=100"

    def test_fails_when_value_absent(self) -> None:
        # arrange
        result = QueryResult(columns=["state"], rows=[("RJ",)], row_count=1)
        # act / assert
        assert (
            ResultSetCheck(expected_value="SP").evaluate(_state_with_result(result))["passed"]
            is False
        )

    def test_fails_without_any_result(self) -> None:
        # arrange — no widget produced a result
        check = ResultSetCheck(expected_value="SP")
        # act
        outcome = check.evaluate(cast(ChatState, {"question": "q"}))
        # assert
        assert outcome["passed"] is False
        assert "no query result" in outcome["reasoning"]


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


_GOLD_A = "SELECT SUM(amount) FROM events"
_GOLD_B = "SELECT SUM(amount + fee) FROM events"


def _any_engine(gold_a: QueryResult, gold_b: QueryResult) -> FakeSqlEngine:
    return FakeSqlEngine(results_by_sql={_GOLD_A: gold_a, _GOLD_B: gold_b})


class TestExecutionMatchAnyCheck:
    """Answer-set tolerance: a candidate matching ANY defensible gold passes."""

    def test_passes_when_candidate_matches_second_gold(self) -> None:
        # arrange — candidate matches the with-fee definition, not the first gold
        gold_a = QueryResult(columns=["s"], rows=[(100.0,)], row_count=1)
        gold_b = QueryResult(columns=["s"], rows=[(115.0,)], row_count=1)
        check = ExecutionMatchAnyCheck([_GOLD_A, _GOLD_B], _any_engine(gold_a, gold_b))
        # act
        result = check.evaluate(_state_with_result(QueryResult(["t"], [(115.0,)], 1)))
        # assert
        assert result["passed"] is True

    def test_fails_when_no_gold_matches(self) -> None:
        # arrange — candidate matches neither definition
        gold_a = QueryResult(columns=["s"], rows=[(100.0,)], row_count=1)
        gold_b = QueryResult(columns=["s"], rows=[(115.0,)], row_count=1)
        check = ExecutionMatchAnyCheck([_GOLD_A, _GOLD_B], _any_engine(gold_a, gold_b))
        # act
        result = check.evaluate(_state_with_result(QueryResult(["t"], [(999.0,)], 1)))
        # assert — reasoning names the gold and candidate row counts
        assert result["passed"] is False
        assert "no widget matched any gold" in result["reasoning"]

    def test_fails_without_query_result(self) -> None:
        # arrange
        gold = QueryResult(columns=["s"], rows=[(1.0,)], row_count=1)
        check = ExecutionMatchAnyCheck([_GOLD_A, _GOLD_B], _any_engine(gold, gold))
        # act
        result = check.evaluate(cast(ChatState, {"question": "q"}))
        # assert
        assert result["passed"] is False
        assert "no query result" in result["reasoning"]

    def test_label_variant_golds_accept_either_spelling(self) -> None:
        # arrange — the same two-group comparison with differently-spelled labels
        gold_a = QueryResult(
            columns=["g", "v"], rows=[("on_time", 4.2), ("late", 2.3)], row_count=2
        )
        gold_b = QueryResult(
            columns=["g", "v"], rows=[("on-time", 4.2), ("late", 2.3)], row_count=2
        )
        check = ExecutionMatchAnyCheck([_GOLD_A, _GOLD_B], _any_engine(gold_a, gold_b))
        candidate = QueryResult(
            columns=["g", "v"], rows=[("on-time", 4.2), ("late", 2.3)], row_count=2
        )
        # act / assert — the hyphen spelling matches gold_b even though gold_a misses
        assert check.evaluate(_state_with_result(candidate))["passed"] is True


class TestResultSetAnyCheck:
    """Scalar answer-set tolerance: any expected value found in any cell passes."""

    def test_passes_when_second_option_matches_a_cell(self) -> None:
        # arrange — the widget holds the with-freight total, not the first option
        result = QueryResult(
            columns=["month", "total"], rows=[("2018-09", 15843553.24)], row_count=1
        )
        check = ResultSetAnyCheck(expected_value_options=["13591643.7", "15843553.2"])
        # act / assert
        assert check.evaluate(_state_with_result(result))["passed"] is True

    def test_fails_when_no_option_matches(self) -> None:
        # arrange
        result = QueryResult(columns=["total"], rows=[(1.0,)], row_count=1)
        check = ResultSetAnyCheck(expected_value_options=["13591643.7", "15843553.2"])
        # act
        outcome = check.evaluate(_state_with_result(result))
        # assert
        assert outcome["passed"] is False
        assert "no cell matched" in outcome["reasoning"]

    def test_fails_without_query_result(self) -> None:
        check = ResultSetAnyCheck(expected_value_options=["1"])
        outcome = check.evaluate(cast(ChatState, {"question": "q"}))
        assert outcome["passed"] is False
        assert "no query result" in outcome["reasoning"]

    def test_restricts_to_named_column(self) -> None:
        # arrange — the value exists, but only outside the named column
        result = QueryResult(columns=["a", "b"], rows=[(42, 7)], row_count=1)
        check = ResultSetAnyCheck(expected_value_options=["42"], column="b")
        # act / assert
        assert check.evaluate(_state_with_result(result))["passed"] is False


class TestDeserializeResultSetAny:
    def test_builds_check_with_options_and_column(self) -> None:
        # arrange
        spec = {"type": "result_set_any", "expected_value_options": ["1", "2"], "column": "total"}
        # act
        check = deserialize_check(
            cast(dict[str, str], spec),
            FakeStructuredChatModel(passed=True, reasoning=""),
            FakeSqlEngine(),
        )
        # assert
        assert isinstance(check, ResultSetAnyCheck)
        assert check.expected_value_options == ["1", "2"]
        assert check.column == "total"


class TestDeserializeExecutionMatchAny:
    def test_builds_check_with_all_gold_options_and_engine(self) -> None:
        # arrange
        engine = FakeSqlEngine()
        judge = FakeStructuredChatModel(passed=True, reasoning="")
        spec = {"type": "execution_match_any", "gold_sql_options": [_GOLD_A, _GOLD_B]}
        # act
        check = deserialize_check(cast(dict[str, str], spec), judge, engine)
        # assert
        assert isinstance(check, ExecutionMatchAnyCheck)
        assert check.gold_sql_options == [_GOLD_A, _GOLD_B]
        assert check.engine is engine


class TestDeserializeExecutionMatchOrderMatters:
    def test_order_matters_flag_reaches_the_check(self) -> None:
        # arrange — the spec can now opt into ordered comparison
        engine = FakeSqlEngine()
        judge = FakeStructuredChatModel(passed=True, reasoning="")
        spec = {"type": "execution_match", "gold_sql": _GOLD_SQL, "order_matters": True}
        # act
        check = deserialize_check(cast(dict[str, str], spec), judge, engine)
        # assert
        assert isinstance(check, ExecutionMatchCheck)
        assert check.order_matters is True

    def test_order_matters_defaults_to_false(self) -> None:
        engine = FakeSqlEngine()
        judge = FakeStructuredChatModel(passed=True, reasoning="")
        check = deserialize_check({"type": "execution_match", "gold_sql": _GOLD_SQL}, judge, engine)
        assert isinstance(check, ExecutionMatchCheck)
        assert check.order_matters is False


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
            "view_present",
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
        state = cast(ChatState, {"question": "Revenue?", "narrative": "Revenue is 42."})
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
        state = cast(ChatState, {"question": "Revenue?", "narrative": "Revenue is 42."})
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
        state = cast(ChatState, {"question": "q", "narrative": "No number here"})
        # act
        result = check.evaluate(state)
        # assert — kills mutmut_34 (reasoning=None) and mutmut_38 (reasoning omitted)
        assert result["reasoning"] == "Missing a specific number"
        assert result["passed"] is False

    def test_evaluate_uses_empty_string_when_question_missing_from_state(self) -> None:
        # arrange — state has no "question" key; default must be ""
        model = FakeStructuredChatModel(passed=True, reasoning="")
        check = RubricCheck(model, rubric="Must state revenue.")
        state = cast(ChatState, {"narrative": "Revenue is 42."})  # no "question" key
        # act
        check.evaluate(state)
        # assert — mutmut_19 uses "XXXX"; mutmut_14/16 use None; correct code uses ""
        combined = " ".join(str(m.content) for m in model.last_runnable.last_messages)
        assert "XXXX" not in combined
        assert "Question: None" not in combined  # kills mutmut_14 (default=None), mutmut_16

    def test_evaluate_uses_empty_string_when_response_missing_from_state(self) -> None:
        # arrange — state has no "narrative" key; default must be ""
        model = FakeStructuredChatModel(passed=True, reasoning="")
        check = RubricCheck(model, rubric="Must state revenue.")
        state = cast(ChatState, {"question": "Revenue?"})  # no "narrative" key
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

    def test_builds_view_present_check(self) -> None:
        # kills deserialize_check mutmut_32/71/72: case "view_present" is missing/mangled
        spec: dict[str, str] = {"type": "view_present"}
        check = deserialize_check(
            spec, FakeStructuredChatModel(passed=True, reasoning=""), FakeSqlEngine()
        )
        assert isinstance(check, ViewPresentCheck)

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


def _view_line(element_id: str, element: dict[str, object]) -> str:
    return json.dumps({"op": "add", "path": f"/elements/{element_id}", "value": element})


def _state_with_view(patch_lines: list[str], query_result: QueryResult) -> ChatState:
    widget = WidgetResult(widget_id="widget-0", title="V", result=query_result, sql="SELECT 1")
    return cast(
        ChatState,
        {
            "question": "Revenue by month",
            "widget_results": [widget],
            "widget_patch_lines": patch_lines,
        },
    )


def _chart(label_column: str, value_columns: list[str]) -> dict[str, object]:
    return {
        "type": "ChartJs",
        "props": {
            "kind": "bar",
            "labelColumn": label_column,
            "valueColumns": value_columns,
            "data": {"$state": "/result/rows"},
        },
        "children": [],
    }


class TestViewIntegrityCheck:
    """ViewIntegrityCheck guards against the LLM binding to columns the result lacks."""

    def test_passes_when_all_referenced_columns_exist(self) -> None:
        # arrange — the chart binds only to real columns
        query_result = QueryResult(columns=["month", "revenue"], rows=[("Jan", 10)], row_count=1)
        lines = [_view_line("chart-1", _chart("month", ["revenue"]))]
        # act
        result = ViewIntegrityCheck().evaluate(_state_with_view(lines, query_result))
        # assert
        assert result["passed"] is True
        assert result["type"] == "view_integrity"
        assert result["value"] == ""
        assert result["reasoning"] == ""

    def test_fails_and_names_missing_chart_column(self) -> None:
        # arrange — chart binds to a column absent from the result
        query_result = QueryResult(columns=["month", "revenue"], rows=[("Jan", 10)], row_count=1)
        lines = [_view_line("chart-1", _chart("month", ["profit"]))]
        # act
        result = ViewIntegrityCheck().evaluate(_state_with_view(lines, query_result))
        # assert
        assert result["passed"] is False
        assert "profit" in result["reasoning"]
        assert result["value"] == ""

    def test_fails_when_kpi_column_missing(self) -> None:
        # arrange — KPI binds to a hallucinated column
        query_result = QueryResult(columns=["month", "revenue"], rows=[("Jan", 10)], row_count=1)
        kpi = {
            "type": "KpiStat",
            "props": {"label": "Total", "valueColumn": "grand_total"},
            "children": [],
        }
        lines = [_view_line("kpi-1", kpi)]
        # act
        result = ViewIntegrityCheck().evaluate(_state_with_view(lines, query_result))
        # assert
        assert result["passed"] is False
        assert "grand_total" in result["reasoning"]

    def test_passes_vacuously_when_no_view_lines(self) -> None:
        # arrange — SQL-failure / narrative-only path: nothing to validate
        state = cast(ChatState, {"question": "q"})
        # act
        result = ViewIntegrityCheck().evaluate(state)
        # assert — kills mutmut_8-20 (type/value/reasoning mutations in early return)
        assert result["passed"] is True
        assert result["type"] == "view_integrity"
        assert result["value"] == ""
        assert result["reasoning"] == ""

    def test_passes_vacuously_when_view_lines_but_no_results(self) -> None:
        # kills mutmut_5 (and → or): when patch_lines exist but results absent, must still pass
        lines = [_view_line("c", _chart("month", ["revenue"]))]
        state = cast(ChatState, {"widget_patch_lines": lines})  # no widget_results
        result = ViewIntegrityCheck().evaluate(state)
        assert result["passed"] is True

    def test_continues_past_element_with_non_dict_props(self) -> None:
        # kills _referenced_columns mutmut_8 (break → continue): later elements still checked
        bad_elem: dict[str, object] = {"type": "KpiStat", "props": "not_a_dict", "children": []}
        good_chart = _chart("hallucinated_col", ["revenue"])
        query_result = QueryResult(
            columns=["revenue"], rows=[(10,)], row_count=1
        )  # no hallucinated_col
        lines = [_view_line("bad", bad_elem), _view_line("good", good_chart)]
        result = ViewIntegrityCheck().evaluate(_state_with_view(lines, query_result))
        # good_chart binds to "hallucinated_col" which isn't in result → should fail
        assert result["passed"] is False
        assert "hallucinated_col" in result["reasoning"]

    def test_recognizes_label_column_prop_by_exact_name(self) -> None:
        # kills _referenced_columns mutmut_14-16 (wrong labelColumn case):
        # a chart whose labelColumn is absent from the result must fail
        query_result = QueryResult(columns=["revenue"], rows=[(10,)], row_count=1)
        lines = [_view_line("c", _chart("month", ["revenue"]))]  # labelColumn="month" not in result
        result = ViewIntegrityCheck().evaluate(_state_with_view(lines, query_result))
        assert result["passed"] is False
        assert "month" in result["reasoning"]


class TestViewPresentCheck:
    """ViewPresentCheck asserts the LLM-authored view is renderable and in-vocabulary."""

    def test_passes_when_a_viz_element_is_present(self) -> None:
        state = cast(
            ChatState, {"widget_patch_lines": [_view_line("c", _chart("month", ["revenue"]))]}
        )
        result = ViewPresentCheck().evaluate(state)
        # kills mutmut_33-54: type/value/reasoning mutations in the success return
        assert result["passed"] is True
        assert result["type"] == "view_present"
        assert result["value"] == ""
        assert result["reasoning"] == ""

    def test_passes_for_the_fallback_data_table(self) -> None:
        table = {"type": "DataTable", "props": {"data": {"$state": "/result"}}, "children": []}
        state = cast(ChatState, {"widget_patch_lines": [_view_line("t", table)]})
        assert ViewPresentCheck().evaluate(state)["passed"] is True

    def test_fails_on_unknown_component(self) -> None:
        bogus = {"type": "Spreadsheet", "props": {}, "children": []}
        state = cast(ChatState, {"widget_patch_lines": [_view_line("x", bogus)]})
        result = ViewPresentCheck().evaluate(state)
        assert result["passed"] is False
        assert "Spreadsheet" in result["reasoning"]
        # kills mutmut_25-30: type/value mutations in the unknown-component return
        assert result["type"] == "view_present"
        assert result["value"] == ""

    def test_fails_when_only_non_viz_elements(self) -> None:
        markdown = {"type": "Markdown", "props": {"text": "hi"}, "children": []}
        state = cast(ChatState, {"widget_patch_lines": [_view_line("m", markdown)]})
        result = ViewPresentCheck().evaluate(state)
        assert result["passed"] is False
        # kills mutmut_40-54: reasoning mutations in the no-viz-element return
        assert result["type"] == "view_present"
        assert result["value"] == ""
        assert result["reasoning"] == "no visualization element"

    def test_fails_when_no_view_lines(self) -> None:
        result = ViewPresentCheck().evaluate(cast(ChatState, {"question": "q"}))
        # kills mutmut_4-8: type/value/reasoning/passed mutations in early return
        assert result["passed"] is False
        assert result["type"] == "view_present"
        assert result["value"] == ""
        assert result["reasoning"] == "no view"

    def test_view_line_with_string_value_is_ignored(self) -> None:
        # kills _added_elements mutmut_9 (and → or): "typed_text" has "type" as substring;
        # with and→or that string would be appended and crash on .get("type")
        non_elem_line = json.dumps({"op": "add", "path": "/x", "value": "typed_text"})
        state = cast(ChatState, {"widget_patch_lines": [non_elem_line]})
        result = ViewPresentCheck().evaluate(state)
        assert result["passed"] is False


class TestViewContainsCheck:
    """ViewContainsCheck asserts the LLM-authored view emits the expected element type."""

    def test_passes_when_element_type_present(self) -> None:
        # arrange — patch_lines add a ChartJs element
        state = cast(
            ChatState, {"widget_patch_lines": [_view_line("c", _chart("month", ["revenue"]))]}
        )
        # act
        result = ViewContainsCheck(element_type="ChartJs").evaluate(state)
        # assert
        assert result["passed"] is True
        assert result["value"] == "ChartJs"

    def test_fails_when_element_type_absent(self) -> None:
        # arrange — only a DataTable, no ChartJs
        table = {"type": "DataTable", "props": {"data": {"$state": "/result"}}, "children": []}
        state = cast(ChatState, {"widget_patch_lines": [_view_line("t", table)]})
        # act
        result = ViewContainsCheck(element_type="ChartJs").evaluate(state)
        # assert
        assert result["passed"] is False
        assert "ChartJs" in result["reasoning"]

    def test_fails_when_no_view_present(self) -> None:
        # arrange — no patch_lines in state at all
        state = cast(ChatState, {"question": "q"})
        # act
        result = ViewContainsCheck(element_type="KpiStat").evaluate(state)
        # assert
        assert result["passed"] is False
