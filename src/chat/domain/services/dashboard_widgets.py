"""Domain service: read a dashboard RenderTree and split it into persistable drafts.

A dashboard's widgets are ``WidgetFrame`` elements keyed ``"<widget-id>-frame"``; each
frame wraps one visualization leaf whose data is bound via ``$state``. These helpers
identify the widgets and extract each into a standalone single-widget spec, so the whole
dashboard *and* every widget on it can each be persisted as its own artifact.
"""

from dataclasses import dataclass

from chat.domain.value_objects.render_tree import RenderElement, RenderTree

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


def widget_leaf(dashboard: RenderTree, widget_id: str) -> RenderElement | None:
    """The widget's visualization element (the frame's single child), if present."""
    frame = dashboard.elements.get(f"{widget_id}{_FRAME_SUFFIX}")
    if frame is None or not frame.children:
        return None
    return dashboard.elements.get(frame.children[0])


def widget_title(dashboard: RenderTree, widget_id: str) -> str:
    """A human title for the widget: its chart ``title`` or KPI ``label``, else its id."""
    leaf = widget_leaf(dashboard, widget_id)
    if leaf is not None:
        for key in ("title", "label"):
            value = leaf.props.get(key)
            if isinstance(value, str) and value:
                return value
    return widget_id


def artifact_drafts(question: str, dashboard: RenderTree) -> list[ArtifactDraft]:
    """Draft the dashboard and each of its widgets as standalone artifacts.

    Returns the full dashboard (titled by the question) first, then one draft per widget
    (each a single-widget spec titled by that widget). A view with no widgets (a text-only
    or fully-failed answer) yields nothing to persist.

    Example:
        drafts = artifact_drafts("Overview", dashboard)  # [dashboard, widget-0, widget-1, ...]
    """
    ids = widget_ids(dashboard)
    if not ids:
        return []
    drafts = [ArtifactDraft(title=question, spec=dashboard)]
    for wid in ids:
        spec = _single_widget_spec(dashboard, wid)
        drafts.append(ArtifactDraft(widget_title(dashboard, wid), spec))
    return drafts


def _single_widget_spec(dashboard: RenderTree, widget_id: str) -> RenderTree:
    """Build a standalone spec holding one widget: root Stack over its frame + its state."""
    frame_id = f"{widget_id}{_FRAME_SUFFIX}"
    elements = {"root": RenderElement(type="Stack", props={}, children=[frame_id])}
    elements.update(_subtree(dashboard, frame_id))
    state = None
    if dashboard.state is not None and widget_id in dashboard.state:
        state = {widget_id: dashboard.state[widget_id]}
    return RenderTree(root="root", elements=elements, state=state)


def _subtree(dashboard: RenderTree, start_id: str) -> dict[str, RenderElement]:
    """Collect the element and every element reachable through its children."""
    collected: dict[str, RenderElement] = {}
    pending = [start_id]
    while pending:
        element_id = pending.pop()
        element = dashboard.elements.get(element_id)
        if element is None or element_id in collected:
            continue
        collected[element_id] = element
        pending.extend(element.children)
    return collected
