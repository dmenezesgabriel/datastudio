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


def compile_view_tree(narrative: str, view_lines: list[str], sql_query: str) -> RenderTree:
    """Compile LLM-authored SpecStream lines into a RenderTree (sync CLI/eval path).

    Builds the deterministic base (root Stack + narrative), applies each JSON-Patch
    line, then appends the SQL disclosure — mirroring what the streaming serializer
    emits, so the batch and streaming views stay equivalent.

    Example:
        tree = compile_view_tree("42 events.", ['{"op":"add",...}'], "SELECT 1")
    """
    elements: dict[str, dict[str, object]] = {
        "root": {"type": "Stack", "props": {}, "children": ["narrative"]},
        "narrative": {"type": "Markdown", "props": {"text": narrative}, "children": []},
    }
    for line in view_lines:
        _apply_view_patch(elements, line)
    if sql_query:
        sql_element = build_markdown_element(f"```sql\n{sql_query}\n```").model_dump()
        elements["sql"] = cast(dict[str, object], sql_element)
        _children(elements).append("sql")
    return RenderTree(root="root", elements={k: _to_element(v) for k, v in elements.items()})


def _children(elements: dict[str, dict[str, object]]) -> list[object]:
    """Return the root Stack's mutable children list."""
    children = elements["root"]["children"]
    return cast(list[object], children) if isinstance(children, list) else []


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
