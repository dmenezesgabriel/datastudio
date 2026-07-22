"""Tests for the read-only schema API backing the composer's mention menu."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chat.application.use_cases.describe_dataset_table import DescribeDatasetTable
from chat.application.use_cases.list_dataset_tables import ListDatasetTables
from chat.infrastructure.api.schema_router import SchemaRouter
from shared.domain.value_objects.table_schema import ColumnDescriptor
from shared.infrastructure.api.error_handlers import register_error_handlers
from test.unit.chat.infrastructure.api.fakes import fake_owner_id
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine


def _client(engine: FakeSqlEngine) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    router = SchemaRouter(
        ListDatasetTables(engine), DescribeDatasetTable(engine), fake_owner_id()
    ).router
    app.include_router(router)
    return TestClient(app)


class TestListTables:
    def test_lists_the_datasets_table_names(self) -> None:
        # arrange
        client = _client(FakeSqlEngine(tables=["events", "customers"]))
        # act
        body = client.get("/api/schema/tables").json()
        # assert
        assert body == {"tables": ["events", "customers"]}

    def test_empty_dataset_returns_an_empty_list(self) -> None:
        # arrange
        client = _client(FakeSqlEngine(tables=[]))
        # act
        body = client.get("/api/schema/tables").json()
        # assert
        assert body == {"tables": []}

    def test_reads_the_engine_rather_than_a_hardcoded_list(self) -> None:
        # The core is data-agnostic: table names are discovered at runtime, never baked in.
        # arrange
        client = _client(FakeSqlEngine(tables=["some_table_named_at_runtime"]))
        # act
        body = client.get("/api/schema/tables").json()
        # assert
        assert body["tables"] == ["some_table_named_at_runtime"]


def _client_with_columns() -> TestClient:
    return _client(
        FakeSqlEngine(
            tables=["events"],
            columns={
                "events": (
                    ColumnDescriptor(name="amount", data_type="DOUBLE"),
                    ColumnDescriptor(name="category", data_type="VARCHAR"),
                )
            },
        )
    )


class TestDescribeTable:
    def test_lists_a_tables_columns_with_their_types(self) -> None:
        # arrange
        client = _client_with_columns()
        # act
        body = client.get("/api/schema/tables/events/columns").json()
        # assert
        assert body == {
            "table": "events",
            "columns": [
                {"name": "amount", "type": "DOUBLE"},
                {"name": "category", "type": "VARCHAR"},
            ],
        }

    def test_unknown_table_returns_404(self) -> None:
        # arrange
        client = _client_with_columns()
        # act
        response = client.get("/api/schema/tables/absent_table/columns")
        # assert
        assert response.status_code == 404

    def test_a_table_with_no_columns_returns_an_empty_list(self) -> None:
        # arrange
        client = _client(FakeSqlEngine(tables=["events"]))
        # act
        body = client.get("/api/schema/tables/events/columns").json()
        # assert
        assert body == {"table": "events", "columns": []}
