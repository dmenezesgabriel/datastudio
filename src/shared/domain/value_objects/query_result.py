"""Immutable value object representing a SQL query result set."""

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryResult:
    """Immutable result of a SQL query execution.

    Example:
        result = QueryResult(columns=["id", "name"], rows=[(1, "Alice")], row_count=1)
        print(result.to_markdown_table())
    """

    columns: list[str]
    rows: list[tuple[object, ...]]
    row_count: int

    def __post_init__(self) -> None:
        """Validate that row_count matches the actual number of rows."""
        if self.row_count != len(self.rows):
            raise ValueError(
                f"row_count={self.row_count!r} does not match len(rows)={len(self.rows)!r}"
            )

    def to_dict_list(self) -> list[dict[str, object]]:
        """Returns each row as a dict keyed by column name."""
        return [dict(zip(self.columns, row, strict=True)) for row in self.rows]

    def to_markdown_table(self) -> str:
        """Returns a GFM pipe table string, or empty string when there are no rows."""
        if not self.rows:
            return ""
        header = "| " + " | ".join(self.columns) + " |"
        separator = "| " + " | ".join("---" for _ in self.columns) + " |"
        data_rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in self.rows]
        return "\n".join([header, separator, *data_rows])
