"""Value object: a lightweight artifact descriptor for the gallery list."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactSummary:
    """An artifact's at-a-glance metadata, enough to list and reopen it.

    ``updated_at`` is a Unix timestamp used to order the gallery most-recent-first;
    ``version_count`` hints at how much revision history the artifact carries.

    Example:
        ArtifactSummary(artifact_id="a-1", title="Revenue overview",
                        updated_at=1751500000.0, version_count=3)
    """

    artifact_id: str
    title: str
    updated_at: float
    version_count: int
