"""Checks over a conversational dashboard edit.

These grade the *edited* dashboard the edit graph produced, not raw graph state: the runner
applies the edit's patches to the prior spec and stashes the merged ``RenderTree`` under
``edited_spec`` (and the classifier's ``edit_mode``). They live apart from the view checks
because they reason over a saved dashboard being mutated in place — did the classifier route
the edit correctly, did the target widget change, and were untouched widgets left intact.
``deserialize_check`` wires them into the factory.
"""

from dataclasses import dataclass, field
from typing import cast

from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.infrastructure.eval._check_base import CheckResult
from chat.infrastructure.graph.chat_state import ChatState

_FRAME_SUFFIX = "-frame"


def _edited_spec(state: ChatState) -> RenderTree | None:
    """The merged dashboard the runner stashed after applying the edit's patches, or None."""
    spec = cast(dict[str, object], state).get("edited_spec")
    return spec if isinstance(spec, RenderTree) else None


def _widget_ids(spec: RenderTree) -> list[str]:
    """The ids of the widgets on the dashboard (a widget owns a ``<id>-frame`` element)."""
    return [k[: -len(_FRAME_SUFFIX)] for k in spec.elements if k.endswith(_FRAME_SUFFIX)]


def _leaf(spec: RenderTree, widget_id: str) -> RenderElement | None:
    """The widget's visualization element (its frame's single child), if present."""
    frame = spec.elements.get(f"{widget_id}{_FRAME_SUFFIX}")
    if frame is None or not frame.children:
        return None
    return spec.elements.get(frame.children[0])


@dataclass
class EditModeCheck:
    """Passes when ``classify_edit`` routed the edit to the expected mode.

    Asserts the router's cheapest-handler choice: a presentational change should be
    ``restyle`` (patch elements, no SQL) and a change needing new data ``reanalyze``.

    Example:
        check = EditModeCheck(expected_mode="restyle")
        result = check.evaluate(state)  # {"type": "edit_mode", "passed": True, ...}
    """

    expected_mode: str

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when state["edit_mode"] equals the expected mode."""
        actual = cast(dict[str, object], state).get("edit_mode")
        passed = actual == self.expected_mode
        reasoning = "" if passed else f"classified as {actual!r}, expected {self.expected_mode!r}"
        return CheckResult(
            type="edit_mode", value=self.expected_mode, passed=passed, reasoning=reasoning
        )


@dataclass
class WidgetKindCheck:
    """Passes when a widget's leaf element is the expected type (optionally a ChartJs kind).

    Grades the edit's effect on the merged dashboard: after "make that a bar chart", the
    target widget's leaf should be a ``ChartJs`` of kind ``bar``. Reads the applied
    ``edited_spec`` (not raw patches), so it catches an in-place ``replace`` of a prop.

    Example:
        check = WidgetKindCheck(widget_id="widget-0", element_type="ChartJs", chart_kind="bar")
        result = check.evaluate(state)  # {"type": "widget_kind", "passed": True, ...}
    """

    widget_id: str
    element_type: str
    chart_kind: str | None = None

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when the widget's leaf matches element_type (and chart_kind if set)."""
        label = self._label()
        spec = _edited_spec(state)
        if spec is None:
            return CheckResult(
                type="widget_kind", value=label, passed=False, reasoning="no edited spec"
            )
        leaf = _leaf(spec, self.widget_id)
        if leaf is None:
            reasoning = f"widget {self.widget_id!r} has no leaf element"
            return CheckResult(type="widget_kind", value=label, passed=False, reasoning=reasoning)
        passed = leaf.type == self.element_type and self._kind_ok(leaf)
        reasoning = "" if passed else f"widget {self.widget_id} is {leaf.type}{self._kind_of(leaf)}"
        return CheckResult(type="widget_kind", value=label, passed=passed, reasoning=reasoning)

    def _kind_ok(self, leaf: RenderElement) -> bool:
        """True when no chart kind is required, or the leaf's kind prop matches it."""
        return self.chart_kind is None or leaf.props.get("kind") == self.chart_kind

    def _kind_of(self, leaf: RenderElement) -> str:
        """A trailing ``" (kind=…)"`` for the reasoning, when the leaf carries a chart kind."""
        kind = leaf.props.get("kind")
        return f" (kind={kind})" if isinstance(kind, str) else ""

    def _label(self) -> str:
        """The check's value label: element type, plus chart kind when required."""
        return (
            self.element_type
            if self.chart_kind is None
            else f"{self.element_type}:{self.chart_kind}"
        )


@dataclass
class WidgetsPreservedCheck:
    """Passes when every listed widget still exists on the edited dashboard.

    Guards against collateral damage: editing one widget must not drop the others. Pair it
    with a restyle/reanalyze on a multi-widget dashboard to assert the untouched widgets
    survived the patch.

    Example:
        check = WidgetsPreservedCheck(widget_ids=["widget-1", "widget-2"])
        result = check.evaluate(state)  # {"type": "widgets_preserved", "passed": True, ...}
    """

    widget_ids: list[str] = field(default_factory=list[str])

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when no listed widget id is missing from the edited dashboard."""
        label = ",".join(self.widget_ids)
        spec = _edited_spec(state)
        if spec is None:
            return CheckResult(
                type="widgets_preserved", value=label, passed=False, reasoning="no edited spec"
            )
        present = set(_widget_ids(spec))
        missing = [wid for wid in self.widget_ids if wid not in present]
        reasoning = "" if not missing else f"dropped widgets: {missing}"
        return CheckResult(
            type="widgets_preserved", value=label, passed=not missing, reasoning=reasoning
        )


@dataclass
class ElementRemovedCheck:
    """Passes when a named element is absent from the edited dashboard.

    Asserts a deletion edit took effect (e.g. "remove the revenue chart" drops
    ``widget-1-frame``). Reads the applied ``edited_spec``.

    Example:
        check = ElementRemovedCheck(element_id="widget-1-frame")
        result = check.evaluate(state)  # {"type": "element_removed", "passed": True, ...}
    """

    element_id: str

    def evaluate(self, state: ChatState) -> CheckResult:
        """Return passed when the element id is no longer present in the edited dashboard."""
        spec = _edited_spec(state)
        if spec is None:
            return CheckResult(
                type="element_removed",
                value=self.element_id,
                passed=False,
                reasoning="no edited spec",
            )
        removed = self.element_id not in spec.elements
        reasoning = "" if removed else f"element {self.element_id!r} still present"
        return CheckResult(
            type="element_removed", value=self.element_id, passed=removed, reasoning=reasoning
        )
