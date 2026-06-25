import math

from shared.domain.value_objects.query_result import QueryResult


def result_sets_match(candidate: QueryResult, gold: QueryResult, order_matters: bool) -> bool:
    """Compare two result sets row-wise with numeric tolerance."""
    if candidate.row_count != gold.row_count:
        return False
    if order_matters:
        return all(_row_covers(c, g) for c, g in zip(candidate.rows, gold.rows, strict=True))
    return _rows_cover_unordered(candidate.rows, gold.rows)


def value_matches(cell: object, expected: str) -> bool:
    """Compare a result cell to an expected string, normalising numeric types.

    Rounds to the precision implied by the expected string (capped at 4 decimals,
    so an unrounded float gold value such as a large SUM is not over-constrained),
    so an unrounded AVG result (6.7741...) matches an expected value of "6.77". A
    relative-tolerance fallback absorbs floating-point summation noise between two
    separate executions of the same query.
    """
    try:
        cell_f = float(str(cell))
        exp_f = float(expected)
        decimals = min(len(expected.split(".")[1]) if "." in expected else 0, 4)
        if round(cell_f, decimals) == round(exp_f, decimals):
            return True
        return math.isclose(cell_f, exp_f, rel_tol=1e-6)
    except (ValueError, TypeError):
        return str(cell).strip().lower() == expected.strip().lower()


def _rows_cover_unordered(
    candidate_rows: list[tuple[object, ...]], gold_rows: list[tuple[object, ...]]
) -> bool:
    """Each gold row must be covered by a distinct, not-yet-used candidate row."""
    used: set[int] = set()
    for gold_row in gold_rows:
        match = next(
            (
                i
                for i, cand_row in enumerate(candidate_rows)
                if i not in used and _row_covers(cand_row, gold_row)
            ),
            None,
        )
        if match is None:
            return False
        used.add(match)
    return True


def _row_covers(candidate_row: tuple[object, ...], gold_row: tuple[object, ...]) -> bool:
    """True when every gold cell value is present in the candidate row (multiset)."""
    pool = list(candidate_row)
    for gold_cell in gold_row:
        match = next(
            (i for i, cell in enumerate(pool) if value_matches(cell, str(gold_cell))),
            None,
        )
        if match is None:
            return False
        pool.pop(match)
    return True
