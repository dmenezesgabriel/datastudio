"""Map a finished ``build_widget`` worker's state update to stream events.

Shared by the build engine (``Text2SqlEngineAdapter``) and the edit engine
(``EditDashboardAdapter``): both fan a widget out through the same worker and surface
its output identically — data first (so ``$state`` exists when the view binds), then
the namespaced view lines, then the SQL disclosure.
"""

from collections.abc import Mapping
from typing import cast

from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    SqlReady,
    ViewPatchLine,
    WidgetDataReady,
)
from chat.domain.value_objects.widget import WidgetResult


def as_list(value: object) -> list[object]:
    """Return value as a list of objects, or empty when it is not a list."""
    return cast(list[object], value) if isinstance(value, list) else []


def widget_events(update: Mapping[str, object]) -> list[ChatStreamEvent]:
    """Map one finished build_widget worker to its data patch, view patches, and SQL.

    Data first (so ``$state`` exists when the view binds), then the namespaced view
    lines, then the SQL disclosure. A failed widget yields only its note view lines.
    """
    results = [r for r in as_list(update.get("widget_results")) if isinstance(r, WidgetResult)]
    lines = [ln for ln in as_list(update.get("widget_patch_lines")) if isinstance(ln, str)]
    events: list[ChatStreamEvent] = [
        WidgetDataReady(widget_id=r.widget_id, result=r.result) for r in results
    ]
    events += [ViewPatchLine(line=line) for line in lines]
    events += [SqlReady(widget_id=r.widget_id, sql=r.sql) for r in results if r.sql]
    return events
