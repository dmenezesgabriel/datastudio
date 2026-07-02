"""Wire-path integrity check: grade the actual SpecStream the browser applies.

Every other check reads the final ``ChatState``. This one reconstructs the stream
events, runs them through the *production* ``SpecStreamSerializer``, applies the emitted
RFC-6902 patches, and validates the resulting json-render spec. It is the only check that
exercises the NDJSON wire — the seam where a ``date``/``Decimal`` serialization crash once
shipped invisibly to the state-based checks. It asserts three things about the real output:
the stream serializes/applies without error (regression guard for that crash class), every
element ``type`` is in the catalogue, and every ``$state`` binding has streamed data behind
it (catching a view authored against data that never reached the wire).
"""

import json
from typing import cast

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.infrastructure.api.spec_stream import SpecStreamSerializer
from chat.infrastructure.eval._check_base import (
    CATALOG_COMPONENTS,
    CheckResult,
    view_lines,
    widget_results,
)

_STATE_BINDING = "$state"


class WireIntegrityCheck:
    """Passes when the serialized SpecStream applies to a catalogue-valid spec.

    Example:
        WireIntegrityCheck().evaluate(state)  # {"type": "wire_integrity", "passed": True, ...}
    """

    def evaluate(self, state: ChatState) -> CheckResult:
        """Serialize the stream, apply it, and validate the resulting spec."""
        try:
            spec = _apply_stream(_events_from_state(state))
        except Exception as exc:  # noqa: BLE001 — any serialize/apply error is a real wire defect
            return _fail(f"stream failed to serialize/apply: {exc!r}")
        problem = _first_problem(spec)
        return _fail(problem) if problem else _pass()


def _events_from_state(state: ChatState) -> list[ChatStreamEvent]:
    """Rebuild the stream events a completed run would have emitted, data-first."""
    results = widget_results(state)
    response = cast(dict[str, object], state).get("response")
    events: list[ChatStreamEvent] = [WidgetDataReady(r.widget_id, r.result) for r in results]
    events += [ViewPatchLine(line=line) for line in view_lines(state)]
    if isinstance(response, str) and response:
        events.append(NarrativeReady(text=response))
    events += [SqlReady(r.widget_id, r.sql) for r in results if r.sql]
    return events


def _apply_stream(events: list[ChatStreamEvent]) -> dict[str, object]:
    """Serialize events through the production serializer and apply every patch line."""
    serializer = SpecStreamSerializer()
    spec: dict[str, object] = {}
    for event in events:
        for line in serializer.lines_for(event):
            _apply_patch(spec, cast(dict[str, object], json.loads(line)))
    return spec


def _apply_patch(spec: dict[str, object], patch: dict[str, object]) -> None:
    """Apply one RFC-6902 add/replace/remove op to the flat spec dict."""
    op, path = patch.get("op"), patch.get("path")
    if not isinstance(op, str) or not isinstance(path, str):
        return
    parts = path.split("/")[1:]
    parent = _walk(spec, parts[:-1]) if parts else None
    if not parts:
        return
    key = parts[-1]
    if op == "remove" and isinstance(parent, dict):
        cast(dict[str, object], parent).pop(key, None)
    elif key == "-" and isinstance(parent, list):
        cast(list[object], parent).append(patch.get("value"))
    elif isinstance(parent, dict):
        cast(dict[str, object], parent)[key] = patch.get("value")


def _walk(node: object, parts: list[str]) -> object:
    """Descend to the parent container, creating missing dict levels along the way."""
    for part in parts:
        if not isinstance(node, dict):
            return None
        node = cast(dict[str, object], node).setdefault(part, {})
    return node


def _first_problem(spec: dict[str, object]) -> str | None:
    """Return the first structural/catalogue/binding violation, or None when valid."""
    elements = spec.get("elements")
    root = spec.get("root")
    if not isinstance(elements, dict):
        return "spec has no /elements map"
    typed_elements = cast(dict[str, object], elements)
    if not isinstance(root, str) or root not in typed_elements:
        return f"root {root!r} not present in /elements"
    state = spec.get("state")
    state_keys: set[str] = set(cast(dict[str, object], state)) if isinstance(state, dict) else set()
    for element_id, element in typed_elements.items():
        problem = _element_problem(element_id, element, typed_elements, state_keys)
        if problem:
            return problem
    return None


def _element_problem(
    element_id: str, element: object, elements: dict[str, object], state_keys: set[str]
) -> str | None:
    """Validate one element's type, child references, and $state bindings."""
    if not isinstance(element, dict):
        return f"element {element_id!r} is not an object"
    typed = cast(dict[str, object], element)
    if typed.get("type") not in CATALOG_COMPONENTS:
        return f"element {element_id!r} has non-catalogue type {typed.get('type')!r}"
    children = typed.get("children")
    for child in cast(list[object], children) if isinstance(children, list) else []:
        if child not in elements:
            return f"element {element_id!r} references missing child {child!r}"
    for binding in _state_bindings(typed.get("props")):
        head = binding.strip("/").split("/")[0]
        if head and head not in state_keys:
            return f"element {element_id!r} binds {binding!r} but no data streamed for it"
    return None


def _state_bindings(value: object) -> list[str]:
    """Collect every ``{"$state": "/..."}`` binding path nested within props."""
    if isinstance(value, dict):
        typed = cast(dict[str, object], value)
        binding = typed.get(_STATE_BINDING)
        if list(typed.keys()) == [_STATE_BINDING] and isinstance(binding, str):
            return [binding]
        return [b for item in typed.values() for b in _state_bindings(item)]
    if isinstance(value, list):
        return [b for item in cast(list[object], value) for b in _state_bindings(item)]
    return []


def _pass() -> CheckResult:
    return {"type": "wire_integrity", "value": "", "passed": True, "reasoning": ""}


def _fail(reason: str) -> CheckResult:
    return {"type": "wire_integrity", "value": "", "passed": False, "reasoning": reason}
