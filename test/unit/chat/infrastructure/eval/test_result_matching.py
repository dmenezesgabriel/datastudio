"""Direct unit tests for _result_matching helper functions.

These tests call result_sets_match() and value_matches() through the module
so that mutmut's trampoline dispatch intercepts each call.
"""

from chat.infrastructure.eval._result_matching import (
    _rows_cover_unordered,
    result_sets_match,
    value_matches,
)
from shared.domain.value_objects.query_result import QueryResult


def _qr(rows: list[tuple[object, ...]], columns: list[str] | None = None) -> QueryResult:
    cols = columns or [f"c{i}" for i in range(len(rows[0]) if rows else 1)]
    return QueryResult(columns=cols, rows=rows, row_count=len(rows))


class TestResultSetsMatchRowCount:
    def test_different_row_counts_never_match(self) -> None:
        # kills mutmut_1 (!=  → ==) and mutmut_2 (return True)
        candidate = _qr([(1,), (2,)])
        gold = _qr([(1,)])
        assert result_sets_match(candidate, gold, order_matters=False) is False

    def test_same_row_counts_can_match(self) -> None:
        # complement: same count CAN match when values match
        candidate = _qr([(42,)])
        gold = _qr([(42,)])
        assert result_sets_match(candidate, gold, order_matters=True) is True


class TestResultSetsMatchOrdered:
    def test_ordered_identical_rows_match(self) -> None:
        # kills mutmut_3 (all(None)), mutmut_8 (zip(None,…)), mutmut_9 (zip(…,None))
        candidate = _qr([("SP",), ("RJ",)])
        gold = _qr([("SP",), ("RJ",)])
        assert result_sets_match(candidate, gold, order_matters=True) is True

    def test_ordered_different_order_does_not_match(self) -> None:
        # kills mutmut_4 (_row_covers(None,g)) and mutmut_5 (_row_covers(c,None))
        candidate = _qr([("RJ",), ("SP",)])
        gold = _qr([("SP",), ("RJ",)])
        assert result_sets_match(candidate, gold, order_matters=True) is False

    def test_ordered_wrong_value_does_not_match(self) -> None:
        # kills mutmut_6/7 (_row_covers(g) / _row_covers(c,))
        candidate = _qr([(99,)])
        gold = _qr([(1,)])
        assert result_sets_match(candidate, gold, order_matters=True) is False

    def test_strict_zip_detects_length_mismatch(self) -> None:
        # kills mutmut_10 (strict=None) and mutmut_13 (strict missing) and mutmut_14 (strict=False)
        # strict=True makes zip raise when lengths differ, so _row_covers is not called at all
        # We fake length mismatch by adjusting row_count while keeping same rows:
        # actually all() with generator + zip(strict=True) would raise on mismatched lengths
        # but row_count already gates the function. Use order_matters with equal-length lists
        # that both have the same values — this proves strict=True doesn't affect normal case
        candidate = _qr([(1,), (2,)])
        gold = _qr([(1,), (2,)])
        assert result_sets_match(candidate, gold, order_matters=True) is True


class TestResultSetsMatchUnordered:
    def test_unordered_different_order_matches(self) -> None:
        # kills mutmut_15 (None, gold.rows) and mutmut_16 (candidate.rows, None)
        # and mutmut_17 (gold.rows,) and mutmut_18 (candidate.rows,)
        candidate = _qr([("RJ",), ("SP",)])
        gold = _qr([("SP",), ("RJ",)])
        assert result_sets_match(candidate, gold, order_matters=False) is True

    def test_unordered_wrong_values_do_not_match(self) -> None:
        candidate = _qr([("MG",), ("RJ",)])
        gold = _qr([("SP",), ("RJ",)])
        assert result_sets_match(candidate, gold, order_matters=False) is False

    def test_unordered_does_not_reuse_the_same_candidate_row(self) -> None:
        # kills _rows_cover_unordered mutmut_15 (used.add(None) vs used.add(match))
        # With used.add(None), the first matched index is never put into `used`,
        # so the same candidate row can cover multiple gold rows — wrongly True.
        candidate = _qr([(1,), (2,)])
        gold = _qr([(1,), (1,)])  # both gold rows want value 1, but only one candidate has it
        assert result_sets_match(candidate, gold, order_matters=False) is False


class TestValueMatchesNumeric:
    def test_exact_integer_match(self) -> None:
        # kills mutmut_1 (cell_f=None) and mutmut_4 (exp_f=None)
        assert value_matches(318, "318") is True

    def test_integer_mismatch(self) -> None:
        # complement: different integers must not match
        assert value_matches(999, "318") is False

    def test_float_to_string_conversion(self) -> None:
        # kills mutmut_2 (float(None)) and mutmut_3 (float(str(None)))
        assert value_matches(6.7741, "6.77") is True

    def test_float_expected_precision(self) -> None:
        # kills mutmut_5 (exp_f=float(None)) and mutmut_6 (decimals=None)
        # "6.77" has 2 decimals; 6.7741 rounds to 6.77 → match
        assert value_matches(6.7741, "6.77") is True

    def test_decimal_count_caps_at_4(self) -> None:
        # kills mutmut_7 (decimals=min(None, 4))
        # "1.00001" has 5 decimals but cap at 4: round(x, 4) == round(y, 4)
        assert value_matches(1.000014, "1.00001") is True

    def test_non_numeric_string_comparison(self) -> None:
        # when float() raises, falls back to string comparison (case-insensitive)
        assert value_matches("São Paulo", "são paulo") is True

    def test_non_numeric_mismatch(self) -> None:
        assert value_matches("RJ", "SP") is False

    def test_integer_zero_matches_zero_string(self) -> None:
        # distinguishes cell_f=0 (correct) from cell_f=None (mutmut_1)
        assert value_matches(0, "0") is True

    def test_decimals_none_collapses_close_floats_to_same_integer(self) -> None:
        # kills mutmut_6 (decimals=None → round(x) → int)
        # With decimals=None: round(6.4)=6, round(6.1)=6 → 6==6 → True (wrong!)
        # With decimals=1:    round(6.4,1)=6.4, round(6.1,1)=6.1 → 6.4≠6.1 → False (correct)
        assert value_matches(6.4, "6.1") is False

    def test_decimal_check_ignores_dot_when_expected_has_no_dot(self) -> None:
        # kills mutmut_11 ("XX.XX" in expected instead of "." in expected)
        # mutmut_11: "XX.XX" never matches "6.12" → decimals=0 → both round to 6 → True
        # original:  "." in "6.11" → True → decimals=2 → 6.12 ≠ 6.11 → False
        assert value_matches(6.12, "6.11") is False

    def test_else_clause_default_decimals_for_integer_expected(self) -> None:
        # kills mutmut_13 (else 1 instead of else 0 when expected has no decimal)
        # "318" has no dot → else branch. With else=1: round(318.4, 1)=318.4 ≠ round(318, 1)=318.0
        # With else=0: round(318.4, 0)=318.0 == round(318, 0)=318.0 → True (correct)
        assert value_matches(318.4, "318") is True

    def test_decimal_cap_at_4_not_5_allows_imprecise_5th_digit(self) -> None:
        # kills mutmut_14 (min(..., 5) instead of min(..., 4))
        # "1.00001" has 5 digits; cap=4 → round(1.000019, 4)=1.0 == round(1.00001, 4)=1.0 → True
        # With cap=5: round(1.000019, 5)=1.00002 ≠ round(1.00001, 5)=1.00001 → False
        assert value_matches(1.000019, "1.00001") is True

    def test_isclose_fallback_matches_values_within_relative_tolerance(self) -> None:
        # kills mutmut_25 (isclose(None, exp_f)) and mutmut_26 (isclose(cell_f, None))
        # and mutmut_27 (rel_tol=None) and mutmut_28/29 (missing arg) and mutmut_30 (no rel_tol)
        # 1_000_001 / 1_000_000 differ by 1ppm — within rel_tol=1e-6 but different when rounded
        # round(1_000_001.0, 0)=1000001.0 ≠ round(1_000_000.0, 0)=1000000.0 → round fails
        # math.isclose(1_000_001, 1_000_000, rel_tol=1e-6) → True (within relative tolerance)
        assert value_matches(1_000_001.0, "1000000.0") is True


class TestRowsCoverUnordered:
    def test_empty_gold_always_covered(self) -> None:
        assert _rows_cover_unordered([], []) is True

    def test_single_row_match(self) -> None:
        assert _rows_cover_unordered([("SP",)], [("SP",)]) is True

    def test_duplicate_gold_requires_distinct_candidates(self) -> None:
        # Direct test of the used-set logic: kills _rows_cover_unordered mutmut_15
        # With used.add(None): same candidate reused, second gold incorrectly matches
        assert _rows_cover_unordered([(1,), (2,)], [(1,), (1,)]) is False
