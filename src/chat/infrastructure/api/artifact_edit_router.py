"""FastAPI router streaming a conversational artifact edit as a json-render SpecStream.

Drives ``EditArtifact`` and serializes its events into patch lines that layer onto the
dashboard the client already holds. Sits under ``/api/artifacts/{id}/edit`` for REST
clarity, though the code lives in chat because the edit drives the LangGraph pipeline.
Separate from the CRUD ``ArtifactsRouter`` to keep the streaming path single-purpose.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from chat.application.ports.artifact_repository import ArtifactRepository
from chat.application.use_cases.edit_artifact import EditArtifact
from chat.domain.errors import ArtifactNotFoundError
from chat.domain.value_objects.stream_event import NarrativeReady
from chat.infrastructure.api.artifact_requests import EditArtifactRequest
from chat.infrastructure.api.spec_stream import SpecStreamSerializer
from shared.infrastructure.api.current_user import ResolveOwnerId
from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)

_STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
_STREAM_ERROR_MESSAGE = "Something went wrong while editing. Please try again."


class ArtifactEditRouter:
    """Builds an APIRouter that streams the EditArtifact use case as SpecStream.

    Example:
        router = ArtifactEditRouter(edit_artifact, repository, resolve_current_user).router
        app.include_router(router)
    """

    def __init__(
        self,
        edit_artifact: EditArtifact,
        repository: ArtifactRepository,
        resolve_current_user: ResolveOwnerId,
    ) -> None:
        """Wire the edit use case, the repository (for a pre-stream 404), and current user."""
        self._edit_artifact = edit_artifact
        self._repository = repository
        self.router = APIRouter()
        self._add_routes(resolve_current_user)

    def _add_routes(self, resolve_current_user: ResolveOwnerId) -> None:
        """Bind the route via a closure so the dependency is a valid ``Depends`` default."""

        async def edit_artifact(
            artifact_id: str,
            request: EditArtifactRequest,
            user_id: Annotated[str, Depends(resolve_current_user)],
        ) -> StreamingResponse:
            return await self._handle_edit(user_id, artifact_id, request.prompt)

        self.router.add_api_route(
            "/api/artifacts/{artifact_id}/edit", edit_artifact, methods=["POST"]
        )

    async def _handle_edit(
        self, user_id: str, artifact_id: str, instruction: str
    ) -> StreamingResponse:
        """404 up front if the artifact is missing/foreign, then stream the edit as NDJSON.

        The existence check runs before the 200 stream starts (a StreamingResponse can no
        longer change status once its body is iterating), so a bad id gets a proper 404.
        """
        if self._repository.get(artifact_id, user_id) is None:
            raise ArtifactNotFoundError(f"artifact {artifact_id!r} not found")
        _logger.info(
            "artifact.edit.received",
            extra={"owner_id": user_id, "artifact_id": artifact_id},
        )
        generator = self._stream_patches(user_id, artifact_id, instruction)
        return StreamingResponse(
            generator, media_type="application/x-ndjson", headers=_STREAM_HEADERS
        )

    async def _stream_patches(
        self, owner_id: str, artifact_id: str, instruction: str
    ) -> AsyncIterator[str]:
        """Serialize edit events to NDJSON; on failure, stream a graceful message."""
        serializer = SpecStreamSerializer.for_edit()
        try:
            async for event in self._edit_artifact.execute(owner_id, artifact_id, instruction):
                for line in serializer.lines_for(event):
                    yield line + "\n"
        except Exception:
            _logger.error("artifact.edit.error", extra={"artifact_id": artifact_id}, exc_info=True)
            for line in serializer.lines_for(NarrativeReady(text=_STREAM_ERROR_MESSAGE)):
                yield line + "\n"
            return
