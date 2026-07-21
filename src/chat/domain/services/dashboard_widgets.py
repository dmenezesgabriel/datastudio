"""Domain service: read a dashboard RenderTree and draft it for persistence.

A dashboard's widgets are ``WidgetFrame`` elements keyed ``"<widget-id>-frame"``; each
frame wraps one visualization leaf whose data is bound via ``$state``. ``widget_ids``
identifies them, and ``artifact_drafts`` turns a dashboard into the single artifact an
answer saves.
"""

from dataclasses import dataclass

from chat.domain.value_objects.render_tree import RenderTree

_FRAME_SUFFIX = "-frame"


@dataclass(frozen=True)
class ArtifactDraft:
    """A persistable artifact-to-be: a display ``title`` and the spec to store.

    Example:
        ArtifactDraft(title="Movies by genre", spec=RenderTree(...))
    """

    title: str
    spec: RenderTree


def widget_ids(dashboard: RenderTree) -> list[str]:
    """The ids of the widgets on the dashboard, in layout order (frame insertion order)."""
    return [key[: -len(_FRAME_SUFFIX)] for key in dashboard.elements if key.endswith(_FRAME_SUFFIX)]


def artifact_drafts(question: str, dashboard: RenderTree) -> list[ArtifactDraft]:
    """Draft the whole dashboard as the single artifact an answer saves.

    One answer saves one artifact — the dashboard, titled by the question — rather than the
    dashboard plus a separate card per widget. Per-widget artifacts flooded the gallery and
    surfaced internal widget ids (e.g. ``widget-1``) as titles (a11y/UX audit MOD-2). A view
    with no widgets (a text-only or fully-failed answer) yields nothing to persist.

    Example:
        artifact_drafts("Overview", dashboard)  # [dashboard]
    """
    if not widget_ids(dashboard):
        return []
    return [ArtifactDraft(title=question, spec=dashboard)]
