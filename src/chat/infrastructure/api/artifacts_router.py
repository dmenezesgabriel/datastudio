"""FastAPI router exposing artifact CRUD, versions, and revert.

Read/write surface for saved dashboards: list the gallery, open one (current spec +
history metadata), preview a specific version, save a new artifact, revert to a
version, and delete. Separate from the streaming edit endpoint (``ArtifactEditRouter``)
to keep each router single-purpose.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from chat.application.ports.artifact_repository import ArtifactRepository
from chat.application.use_cases.save_artifact import SaveArtifact
from chat.application.use_cases.set_artifact_version import SetArtifactVersion
from chat.domain.entities.artifact import Artifact
from chat.domain.errors import ArtifactNotFoundError
from chat.infrastructure.api.artifact_requests import RevertArtifactRequest, SaveArtifactRequest
from shared.infrastructure.api.current_user import ResolveOwnerId


class ArtifactsRouter:
    """Builds an APIRouter for the artifact gallery, versions, and revert.

    Reads go straight to the repository (matching the conversations read router);
    writes go through use cases so invariants stay in the domain.

    Example:
        router = ArtifactsRouter(repo, save, set_version, resolve_current_user).router
        app.include_router(router)
    """

    def __init__(
        self,
        repository: ArtifactRepository,
        save_artifact: SaveArtifact,
        set_artifact_version: SetArtifactVersion,
        resolve_current_user: ResolveOwnerId,
    ) -> None:
        """Wire the repository, write use cases, and current-user dependency; add routes."""
        self._repository = repository
        self._save_artifact = save_artifact
        self._set_artifact_version = set_artifact_version
        self.router = APIRouter()
        self._add_read_routes(resolve_current_user)
        self._add_write_routes(resolve_current_user)

    def _add_read_routes(self, resolve_current_user: ResolveOwnerId) -> None:
        """Bind the gallery-list, open, and version-preview reads."""

        async def list_artifacts(
            user_id: Annotated[str, Depends(resolve_current_user)],
        ) -> dict[str, object]:
            return self._list(user_id)

        async def get_artifact(
            artifact_id: str, user_id: Annotated[str, Depends(resolve_current_user)]
        ) -> dict[str, object]:
            return _artifact_view(self._load(user_id, artifact_id))

        async def get_version(
            artifact_id: str, index: int, user_id: Annotated[str, Depends(resolve_current_user)]
        ) -> dict[str, object]:
            return self._version(user_id, artifact_id, index)

        self.router.add_api_route("/api/artifacts", list_artifacts, methods=["GET"])
        self.router.add_api_route("/api/artifacts/{artifact_id}", get_artifact, methods=["GET"])
        self.router.add_api_route(
            "/api/artifacts/{artifact_id}/versions/{index}", get_version, methods=["GET"]
        )

    def _add_write_routes(self, resolve_current_user: ResolveOwnerId) -> None:
        """Bind the save, revert, and delete writes."""

        async def save_artifact(
            request: SaveArtifactRequest, user_id: Annotated[str, Depends(resolve_current_user)]
        ) -> dict[str, object]:
            artifact_id = self._save_artifact.execute(user_id, request.title, request.spec)
            return {"artifact_id": artifact_id}

        async def revert_artifact(
            artifact_id: str,
            request: RevertArtifactRequest,
            user_id: Annotated[str, Depends(resolve_current_user)],
        ) -> dict[str, object]:
            artifact = self._set_artifact_version.execute(user_id, artifact_id, request.index)
            return _artifact_view(artifact)

        async def delete_artifact(
            artifact_id: str, user_id: Annotated[str, Depends(resolve_current_user)]
        ) -> dict[str, object]:
            self._repository.delete(artifact_id, user_id)
            return {"deleted": artifact_id}

        self.router.add_api_route("/api/artifacts", save_artifact, methods=["POST"])
        self.router.add_api_route(
            "/api/artifacts/{artifact_id}/revert", revert_artifact, methods=["POST"]
        )
        self.router.add_api_route(
            "/api/artifacts/{artifact_id}", delete_artifact, methods=["DELETE"]
        )

    def _list(self, owner_id: str) -> dict[str, object]:
        """Return gallery summaries of the caller's artifacts, most-recent first."""
        summaries = self._repository.list_summaries(owner_id)
        return {
            "artifacts": [
                {
                    "artifact_id": s.artifact_id,
                    "title": s.title,
                    "updated_at": s.updated_at,
                    "version_count": s.version_count,
                }
                for s in summaries
            ]
        }

    def _version(self, owner_id: str, artifact_id: str, index: int) -> dict[str, object]:
        """Return one stored version's spec, or 404 if the version is out of range."""
        artifact = self._load(owner_id, artifact_id)
        if not 0 <= index < len(artifact.versions):
            raise ArtifactNotFoundError(f"artifact {artifact_id!r} has no version {index}")
        return {"spec": artifact.versions[index].spec.model_dump()}

    def _load(self, owner_id: str, artifact_id: str) -> Artifact:
        """Fetch the caller's artifact or raise 404 (absent or not theirs)."""
        artifact = self._repository.get(artifact_id, owner_id)
        if artifact is None:
            raise ArtifactNotFoundError(f"artifact {artifact_id!r} not found")
        return artifact


def _artifact_view(artifact: Artifact) -> dict[str, object]:
    """Serialize an artifact as its current spec plus version-history metadata."""
    return {
        "artifact_id": artifact.artifact_id,
        "title": artifact.title,
        "current": artifact.current,
        "spec": artifact.current_spec.model_dump(),
        "versions": [
            {"index": i, "instruction": v.instruction, "created_at": v.created_at}
            for i, v in enumerate(artifact.versions)
        ],
    }
