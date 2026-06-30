"""Incremental events emitted while answering one question.

The text2sql engine yields these as the dashboard is built, so the transport layer
can render it widget-by-widget. They are pure data — no json-render wire format or
HTTP concern leaks in here; the infrastructure layer translates them into a
json-render SpecStream.

Order over a run: ``ProgressUpdate`` (schema/planning), then per widget (as each
parallel worker finishes) a ``WidgetDataReady`` (its rows, streamed as a backend
``/state`` patch — never through the LLM) followed by its ``ViewPatchLine``s (the
LLM-authored visualization bound to ``$state``) and a ``SqlReady`` (its disclosure),
then one ``NarrativeReady`` (the deterministic overall summary).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from shared.domain.value_objects.query_result import QueryResult


@dataclass(frozen=True)
class ProgressUpdate:
    """A pipeline stage completed, so the UI can show what's happening.

    Example:
        ProgressUpdate(stage="plan_widgets")
    """

    stage: str


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
        SqlReady(widget_id="widget-0", sql_query="SELECT count(*) FROM orders")
    """

    widget_id: str
    sql_query: str


@dataclass(frozen=True)
class NarrativeReady:
    """The deterministic overall summary (exact numbers) across the widgets.

    Example:
        NarrativeReady(text="Revenue grew 12% over the year across 5 categories.")
    """

    text: str


ChatStreamEvent = ProgressUpdate | WidgetDataReady | ViewPatchLine | SqlReady | NarrativeReady
"""Union of everything the engine can yield for a single answered question."""

TypedChatStream = AsyncIterator[ChatStreamEvent]
"""An async stream of events for one answered question.

Lives in the domain (not ``infrastructure/types.py``) because the application-layer
``Text2SqlPort`` returns it and so cannot depend on an infrastructure alias.
"""
