"""FastAPI router exposing the connected dataset's schema.

Read-only support for the composer's ``@`` mention menu: the client needs the real table
names to offer, so a question carries an identifier the engine actually has. Separate from
``ChatRouter`` (which streams answers) to keep each router single-purpose.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from chat.application.use_cases.list_dataset_tables import ListDatasetTables
from shared.infrastructure.api.current_user import ResolveOwnerId


class SchemaRouter:
    """Builds an APIRouter for reading the dataset's schema.

    Example:
        router = SchemaRouter(list_dataset_tables, resolve_current_user).router
        app.include_router(router)
    """

    def __init__(
        self, list_dataset_tables: ListDatasetTables, resolve_current_user: ResolveOwnerId
    ) -> None:
        """Wire the use case and current-user dependency, then register the read routes."""
        self._list_dataset_tables = list_dataset_tables
        self.router = APIRouter()
        self._add_routes(resolve_current_user)

    def _add_routes(self, resolve_current_user: ResolveOwnerId) -> None:
        """Bind routes via closures so the dependency is a valid ``Depends`` default."""

        # The dataset is shared rather than owned, so the caller's id does not scope the
        # result — the dependency is still required, so an unauthenticated caller cannot
        # enumerate the schema.
        async def list_tables(
            _user_id: Annotated[str, Depends(resolve_current_user)],
        ) -> dict[str, list[str]]:
            return {"tables": self._list_dataset_tables.execute()}

        self.router.add_api_route("/api/schema/tables", list_tables, methods=["GET"])
