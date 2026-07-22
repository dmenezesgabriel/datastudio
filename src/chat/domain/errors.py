"""Chat component domain errors — concrete cases extending the shared categories."""

from shared.domain.errors import NotFoundError


class ConversationNotFoundError(NotFoundError):
    """The requested conversation does not exist or is not owned by the caller."""


class ArtifactNotFoundError(NotFoundError):
    """The requested artifact does not exist or is not owned by the caller."""


class TableNotFoundError(NotFoundError):
    """The requested table is not one the connected dataset lists."""
