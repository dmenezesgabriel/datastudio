import pytest

from shared.domain.value_objects.query_result import QueryResult


class TestQueryResult:
    def test_construction_succeeds_when_row_count_matches(self) -> None:
        result = QueryResult(columns=["id"], rows=[(1,)], row_count=1)
        assert result.row_count == 1

    def test_raises_when_row_count_mismatches(self) -> None:
        with pytest.raises(ValueError, match="row_count=2.*len\\(rows\\)=1"):
            QueryResult(columns=["id"], rows=[(1,)], row_count=2)

    def test_to_dict_list_zips_columns_and_rows(self) -> None:
        result = QueryResult(columns=["id", "name"], rows=[(1, "Alice")], row_count=1)
        assert result.to_dict_list() == [{"id": 1, "name": "Alice"}]

    def test_to_dict_list_returns_empty_for_no_rows(self) -> None:
        result = QueryResult(columns=["id"], rows=[], row_count=0)
        assert result.to_dict_list() == []

    def test_to_markdown_table_includes_header_and_separator(self) -> None:
        result = QueryResult(columns=["a", "b"], rows=[(1, 2)], row_count=1)
        table = result.to_markdown_table()
        assert "| a | b |" in table
        assert "| --- | --- |" in table

    def test_to_markdown_table_includes_data_rows(self) -> None:
        result = QueryResult(columns=["x"], rows=[(42,)], row_count=1)
        assert "| 42 |" in result.to_markdown_table()

    def test_to_markdown_table_returns_empty_string_for_no_rows(self) -> None:
        result = QueryResult(columns=["x"], rows=[], row_count=0)
        assert result.to_markdown_table() == ""
