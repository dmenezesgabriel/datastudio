from dataclasses import dataclass

from shared.domain.value_objects.query_result import QueryResult


@dataclass(frozen=True)
class SubQueryResult:
    """Result of executing one decomposed sub-question.

    Example:
        sub = SubQueryResult(
            question="Average MPG in 1970?",
            sql="SELECT AVG(mpg) FROM cars WHERE year = 1970",
            result=QueryResult(columns=["avg"], rows=[(17.1,)], row_count=1),
        )
    """

    question: str
    sql: str
    result: QueryResult
