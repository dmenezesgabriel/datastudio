"""Incremental events emitted while answering one question.

The text2sql engine yields these as the dashboard is built, so the transport layer
can render it widget-by-widget. They are pure data — no json-render wire format or
HTTP concern leaks in here; the infrastructure layer translates them into a
json-render SpecStream.

Order over a run: ``ProgressStep``s (each pipeline step transitioning through
running → done/failed, so the UI can render a live checklist), interleaved with the
per-widget payload — a ``WidgetDataReady`` (its rows, streamed as a backend ``/state``
patch — never through the LLM) followed by its ``ViewPatchLine``s (the LLM-authored
visualization bound to ``$state``) and a ``SqlReady`` (its disclosure) — then one
``NarrativeReady`` (the deterministic overall summary).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from shared.domain.value_objects.query_result import QueryResult

ProgressStatus = Literal["running", "done", "failed"]
"""Lifecycle of a single progress step as it is surfaced to the checklist."""


@dataclass(frozen=True)
class ProgressStep:
    """One pipeline step's state, so the UI can render/advance a live checklist.

    A step is identified by ``step_id`` (stable across its running→done transition) and
    may nest under a parent step via ``parent_id`` — e.g. a widget's "Generating SQL"
    child nests under its "Building <widget>" parent.

    Example:
        ProgressStep(step_id="plan_widgets", label="Planning the dashboard", status="running")
        ProgressStep(step_id="widget-0:sql", label="Generating SQL", status="done",
                     parent_id="widget-0")
    """

    step_id: str
    label: str
    status: ProgressStatus
    parent_id: str | None = None


@dataclass(frozen=True)
class WidgetDataReady:
    """One widget's rows, to be streamed as a backend-authored ``/state/<id>`` patch.

    The data is supplied out of the view-authoring model: the LLM only emits
    elements bound to ``$state:"/<widget_id>/rows"``; this carries the values.

    Example:
        WidgetDataReady(widget_id="widget-0", result=QueryResult(...))
    """

    widget_id: str
    result: QueryResult


@dataclass(frozen=True)
class ViewPatchLine:
    """One validated SpecStream JSON-Patch line authored by a widget's view node.

    Example:
        ViewPatchLine(line='{"op":"add","path":"/elements/widget-0-chart","value":{...}}')
    """

    line: str


@dataclass(frozen=True)
class SqlReady:
    """The SQL that produced one widget, for its deterministic SQL disclosure.

    Example:
        SqlReady(widget_id="widget-0", sql="SELECT count(*) FROM events")
    """

    widget_id: str
    sql: str


@dataclass(frozen=True)
class NarrativeReady:
    """The deterministic overall summary (exact numbers) across the widgets.

    Example:
        NarrativeReady(text="The total is 42 across 5 categories.")
    """

    text: str


ChatStreamEvent = ProgressStep | WidgetDataReady | ViewPatchLine | SqlReady | NarrativeReady
"""Union of everything the engine can yield for a single answered question."""

TypedChatStream = AsyncIterator[ChatStreamEvent]
"""An async stream of events for one answered question.

Lives in the domain (not ``infrastructure/types.py``) because the application-layer
``Text2SqlPort`` returns it and so cannot depend on an infrastructure alias.
"""
