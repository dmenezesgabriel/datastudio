"""json-render tree helpers for the narrative and the sync (CLI/eval) view path.

The visualization itself is authored by the LLM as a SpecStream (see the
``generate_widget_view`` node); this module only builds the deterministic narrative
element and compiles a stream of LLM patches into a ``RenderTree`` for the batch
path. The emitted component ``type`` names and prop shapes must stay in sync with
the frontend Zod catalogue (``frontend/src/catalog.ts``).
"""

from typing import cast

from chat.domain.value_objects.dashboard_layout import GRID_REGION, KPI_REGION, frame_id
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.infrastructure.graph.spec_patch import parse_patch


def build_markdown_element(text: str) -> RenderElement:
    """Build a narrative/answer Markdown element."""
    props: dict[str, object] = {"text": text}
    return RenderElement(type="Markdown", props=props, children=[])


def narrative_tree(narrative: str) -> RenderTree:
    """Build a tree with only the narrative answer (used on the SQL-failure path)."""
    elements = {
        "narrative": build_markdown_element(narrative),
        "root": RenderElement(type="Stack", props={}, children=["narrative"]),
    }
    return RenderTree(root="root", elements=elements)


def compile_render_tree(
    narrative: str, patch_lines: list[str], sql_by_widget: dict[str, str]
) -> RenderTree:
    """Compile LLM-authored SpecStream lines into a RenderTree (sync CLI/eval path).

    Builds the deterministic F-layout base (root Stack over narrative → KpiRow band →
    Grid), applies each JSON-Patch line (each widget wraps its leaf in a WidgetFrame and
    namespaces itself into the band or the grid), then fills each frame's SQL — mirroring
    what the streaming serializer emits, so the batch and streaming views stay equivalent.

    Example:
        tree = compile_render_tree("42 events.", ['{"op":"add",...}'], {"widget-0": "SELECT 1"})
    """
    elements: dict[str, dict[str, object]] = {
        "root": {"type": "Stack", "props": {}, "children": ["narrative", KPI_REGION, GRID_REGION]},
        "narrative": {"type": "Markdown", "props": {"text": narrative}, "children": []},
        KPI_REGION: {"type": "KpiRow", "props": {}, "children": []},
        GRID_REGION: {"type": "Grid", "props": {}, "children": []},
    }
    for line in patch_lines:
        _apply_view_patch(elements, line)
    _set_frame_sql(elements, sql_by_widget)
    return RenderTree(root="root", elements={k: _to_element(v) for k, v in elements.items()})


def _set_frame_sql(elements: dict[str, dict[str, object]], sql_by_widget: dict[str, str]) -> None:
    """Set each widget frame's ``sql`` prop (the frame was added by the widget's view patches).

    Mirrors the streaming serializer's per-widget ``/props/sql`` replace, so the batch and
    streaming views hold SQL identically. A widget whose view produced no frame is skipped.
    """
    for widget_id, sql in sql_by_widget.items():
        frame = elements.get(frame_id(widget_id))
        props = frame.get("props") if isinstance(frame, dict) else None
        if isinstance(props, dict):
            cast(dict[str, object], props)["sql"] = sql


def _apply_view_patch(elements: dict[str, dict[str, object]], line: str) -> None:
    """Apply one RFC-6902 patch line to the flat ``elements`` map, ignoring bad lines."""
    patch = parse_patch(line)
    if patch is None:
        return
    op, path = patch.get("op"), patch.get("path")
    if not isinstance(op, str) or not isinstance(path, str) or not path.startswith("/elements/"):
        return
    try:
        _write_path(elements, path.split("/")[2:], op, patch.get("value"))
    except (KeyError, TypeError, IndexError):
        return  # patch referenced a missing element/field — skip it


def _write_path(
    elements: dict[str, dict[str, object]], parts: list[str], op: str, value: object
) -> None:
    """Add/replace/remove ``value`` at ``parts`` within the elements map."""
    if len(parts) == 1:
        if op == "remove":
            elements.pop(parts[0], None)
        elif isinstance(value, dict):
            elements[parts[0]] = cast(dict[str, object], value)
        return
    target: object = elements
    for part in parts[:-1]:
        if not isinstance(target, dict):
            return
        target = cast(dict[str, object], target)[part]
    leaf = parts[-1]
    if leaf == "-" and isinstance(target, list):
        cast(list[object], target).append(value)
    elif isinstance(target, dict):
        cast(dict[str, object], target)[leaf] = value


def _to_element(element_dict: dict[str, object]) -> RenderElement:
    """Coerce a (possibly LLM-authored) element dict into a RenderElement, with defaults."""
    props = element_dict.get("props")
    children = element_dict.get("children")
    return RenderElement(
        type=str(element_dict.get("type", "Markdown")),
        props=cast(dict[str, object], props) if isinstance(props, dict) else {},
        children=[c for c in cast(list[object], children) if isinstance(c, str)]
        if isinstance(children, list)
        else [],
    )


def apply_patch_lines(base: RenderTree, patch_lines: list[str]) -> RenderTree:
    """Apply RFC-6902 patch lines to an existing tree, returning the edited tree.

    The edit counterpart of ``compile_render_tree``: instead of building from the
    F-layout base, it mutates a *saved* dashboard (``/elements``, ``/state`` and ``/root``
    paths) so an artifact edit reuses only the widgets the instruction changed. Appending
    a child id already present is a no-op, so a reanalyzed widget that reuses its id
    overwrites its elements in place without duplicating its frame in the region.

    Example:
        edited = apply_patch_lines(spec, ['{"op":"replace","path":"/elements/w0/props/kind",...}'])
    """
    doc = base.model_dump()
    if doc.get("state") is None:
        doc["state"] = {}
    for line in patch_lines:
        _apply_patch(doc, line)
    return RenderTree.model_validate(doc)


def _apply_patch(doc: dict[str, object], line: str) -> None:
    """Apply one RFC-6902 patch line to the mutable document, ignoring malformed ops."""
    patch = parse_patch(line)
    if patch is None:
        return
    op, path = patch.get("op"), patch.get("path")
    if not isinstance(op, str) or not isinstance(path, str) or not path.startswith("/"):
        return
    tokens = [_unescape(token) for token in path.split("/")[1:]]
    if not tokens:
        return
    try:
        parent = _navigate(doc, tokens[:-1])
        _apply_op(parent, tokens[-1], op, patch.get("value"))
    except (KeyError, IndexError, TypeError, ValueError):
        return  # patch referenced a missing/mistyped location — skip it


def _unescape(token: str) -> str:
    """Decode JSON-Pointer escapes (``~1`` -> ``/``, ``~0`` -> ``~``)."""
    return token.replace("~1", "/").replace("~0", "~")


def _navigate(node: object, tokens: list[str]) -> object:
    """Walk into ``node`` following pointer ``tokens``, raising when a step is invalid."""
    for token in tokens:
        if isinstance(node, list):
            node = cast(list[object], node)[int(token)]
        elif isinstance(node, dict):
            node = cast(dict[str, object], node)[token]
        else:
            raise TypeError(f"cannot descend into {type(node).__name__} at {token!r}")
    return node


def _apply_op(parent: object, leaf: str, op: str, value: object) -> None:
    """Add/replace/remove ``value`` at ``leaf`` within its parent container."""
    if op == "remove":
        _remove(parent, leaf)
    elif op in ("add", "replace"):
        _set(parent, leaf, op, value)


def _set(parent: object, leaf: str, op: str, value: object) -> None:
    """Set ``value`` at ``leaf``; appending an already-present list item is a no-op."""
    if isinstance(parent, list):
        target = cast(list[object], parent)
        if leaf == "-":
            if value not in target:  # idempotent: a reused widget id won't duplicate its frame
                target.append(value)
        elif op == "add":
            target.insert(int(leaf), value)
        else:
            target[int(leaf)] = value
    elif isinstance(parent, dict):
        cast(dict[str, object], parent)[leaf] = value
    else:
        raise TypeError(f"cannot set {leaf!r} on {type(parent).__name__}")


def _remove(parent: object, leaf: str) -> None:
    """Remove ``leaf`` from its parent container (a missing key is ignored)."""
    if isinstance(parent, list):
        cast(list[object], parent).pop(int(leaf))
    elif isinstance(parent, dict):
        cast(dict[str, object], parent).pop(leaf, None)
    else:
        raise TypeError(f"cannot remove {leaf!r} from {type(parent).__name__}")
