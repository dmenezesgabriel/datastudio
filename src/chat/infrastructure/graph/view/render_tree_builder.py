"""json-render tree helpers for the narrative and the sync (CLI/eval) view path.

The visualization itself is authored by the LLM as a SpecStream (see the
``generate_view`` node); this module only builds the deterministic narrative
element and compiles a stream of LLM patches into a ``RenderTree`` for the batch
path. The emitted component ``type`` names and prop shapes must stay in sync with
the frontend Zod catalogue (``frontend/src/catalog.ts``).
"""

from typing import cast

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


def compile_view_tree(
    narrative: str, view_lines: list[str], sql_by_widget: dict[str, str]
) -> RenderTree:
    """Compile LLM-authored SpecStream lines into a RenderTree (sync CLI/eval path).

    Builds the deterministic F-layout base (root Stack over narrative → KpiRow band →
    Grid), applies each JSON-Patch line (each widget wraps its leaf in a WidgetFrame and
    namespaces itself into the band or the grid), then fills each frame's SQL — mirroring
    what the streaming serializer emits, so the batch and streaming views stay equivalent.

    Example:
        tree = compile_view_tree("42 events.", ['{"op":"add",...}'], {"widget-0": "SELECT 1"})
    """
    elements: dict[str, dict[str, object]] = {
        "root": {"type": "Stack", "props": {}, "children": ["narrative", "kpi-row", "grid"]},
        "narrative": {"type": "Markdown", "props": {"text": narrative}, "children": []},
        "kpi-row": {"type": "KpiRow", "props": {}, "children": []},
        "grid": {"type": "Grid", "props": {}, "children": []},
    }
    for line in view_lines:
        _apply_view_patch(elements, line)
    _set_frame_sql(elements, sql_by_widget)
    return RenderTree(root="root", elements={k: _to_element(v) for k, v in elements.items()})


def _set_frame_sql(elements: dict[str, dict[str, object]], sql_by_widget: dict[str, str]) -> None:
    """Set each widget frame's ``sql`` prop (the frame was added by the widget's view patches).

    Mirrors the streaming serializer's per-widget ``/props/sql`` replace, so the batch and
    streaming views hold SQL identically. A widget whose view produced no frame is skipped.
    """
    for widget_id, sql in sql_by_widget.items():
        frame = elements.get(f"{widget_id}-frame")
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


def _to_element(raw: dict[str, object]) -> RenderElement:
    """Coerce a (possibly LLM-authored) element dict into a RenderElement, with defaults."""
    props = raw.get("props")
    children = raw.get("children")
    return RenderElement(
        type=str(raw.get("type", "Markdown")),
        props=cast(dict[str, object], props) if isinstance(props, dict) else {},
        children=[c for c in cast(list[object], children) if isinstance(c, str)]
        if isinstance(children, list)
        else [],
    )
