"""Tests for the read-only schema API backing the composer's mention menu."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chat.application.use_cases.list_dataset_tables import ListDatasetTables
from chat.infrastructure.api.schema_router import SchemaRouter
from shared.infrastructure.api.error_handlers import register_error_handlers
from test.unit.chat.infrastructure.api.fakes import fake_owner_id
from test.unit.shared.infrastructure.sql_engine.fake_sql_engine import FakeSqlEngine


def _client(engine: FakeSqlEngine) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(SchemaRouter(ListDatasetTables(engine), fake_owner_id()).router)
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
