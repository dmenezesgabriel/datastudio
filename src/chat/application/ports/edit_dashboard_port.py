"""Port interface for editing a saved dashboard through the edit pipeline."""

from typing import Protocol, runtime_checkable

from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.stream_event import TypedChatStream


@runtime_checkable
class EditDashboardPort(Protocol):
    """Contract for applying a natural-language edit to an existing dashboard spec.

    Hides the LangGraph edit pipeline from the application layer. Given the current
    dashboard and an instruction, it streams the same event vocabulary as a build
    (progress, then per-widget data/view/SQL patches) — the patches target existing
    element ids so the caller applies them to the artifact's current spec.

    Example:
        engine: EditDashboardPort = EditDashboardAdapter(graph, timeout_s=120.0)
        async for event in engine.edit(spec, "make the revenue chart a line chart"):
            ...
    """

    def edit(self, spec: RenderTree, instruction: str) -> TypedChatStream:
        """Stream the patch events that apply ``instruction`` to ``spec``."""
        ...
