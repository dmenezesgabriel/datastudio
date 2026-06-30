"""Value objects for the multi-widget dashboard pipeline.

A dashboard answer fans out into one widget per sub-question. ``WidgetSpec`` is the
planned intent for a widget (its id is assigned by the orchestrator so ``$state``
paths never collide); ``WidgetResult`` bundles a widget's executed query rows with
the SQL that produced them, for the in-stream ``/state`` patch and SQL disclosure.
"""

from dataclasses import dataclass

from shared.domain.value_objects.query_result import QueryResult


@dataclass(frozen=True)
class WidgetSpec:
    """A planned dashboard widget: a titled sub-question to answer and visualize.

    Example:
        WidgetSpec(id="widget-0", title="Revenue by month", sub_question="monthly revenue")
    """

    id: str
    title: str
    sub_question: str


@dataclass(frozen=True)
class WidgetResult:
    """A widget's executed result: its title, rows (for the ``/state`` patch), and SQL.

    Example:
        WidgetResult(widget_id="widget-0", title="Revenue", result=QueryResult(...), sql="SELECT 1")
    """

    widget_id: str
    title: str
    result: QueryResult
    sql: str
