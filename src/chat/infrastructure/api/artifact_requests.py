"""Request payloads for the artifact CRUD endpoints."""

from pydantic import BaseModel, Field

from chat.domain.value_objects.render_tree import RenderTree


class SaveArtifactRequest(BaseModel):
    """A dashboard to save: a display ``title`` plus the json-render ``spec`` to store.

    The client posts the spec it already rendered, so saving reads nothing back from
    the originating conversation.

    Example:
        SaveArtifactRequest(title="Revenue overview", spec=RenderTree(...))
    """

    title: str
    spec: RenderTree


class RevertArtifactRequest(BaseModel):
    """Selects which stored version an artifact should point at (revert / navigate).

    Example:
        RevertArtifactRequest(index=0)  # back to the first saved version
    """

    index: int


class EditArtifactRequest(BaseModel):
    """A natural-language edit to apply to an artifact's current dashboard.

    Matches the body json-render's ``useUIStream`` hook POSTs (``{prompt, context,
    currentSpec}``); only ``prompt`` — the edit instruction — is read, and ``currentSpec``
    is ignored because the server is authoritative for the artifact's spec.

    Example:
        EditArtifactRequest(prompt="make the revenue chart a line chart")
    """

    prompt: str
    context: dict[str, object] = Field(default_factory=dict)
