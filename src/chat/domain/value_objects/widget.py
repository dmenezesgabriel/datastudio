"""Value objects for the multi-widget dashboard pipeline.

A dashboard answer fans out into one widget per sub-question. ``WidgetSpec`` is the
planned intent for a widget (its id is assigned by the orchestrator so ``$state``
paths never collide); ``WidgetResult`` bundles a widget's executed query rows with
the SQL that produced them, for the in-stream ``/state`` patch and SQL disclosure.
"""

from dataclasses import dataclass
from typing import Literal

from shared.domain.value_objects.query_result import QueryResult

# A widget's planning role, declared by the orchestrator and mapped deterministically to an
# F-layout region by the host (never inferred from the element the worker authors):
#   "metric"   — one headline number, shown as a KpiStat in the top KPI band.
#   "analysis" — a trend, breakdown, or detail list, shown as a chart/table in the grid.
WidgetRole = Literal["metric", "analysis"]

# A presentation the user explicitly asked for ("show it as a table/chart/kpi"), captured by
# the planner and honoured by the view author, overriding its data-shape default. ``None`` when
# the user named no preference, leaving the choice to the data shape.
WidgetViewHint = Literal["table", "chart", "kpi"]


@dataclass(frozen=True)
class WidgetSpec:
    """A planned dashboard widget: a titled sub-question to answer and visualize.

    ``role`` is the planner's intent (metric vs analysis); the host maps it to the KPI
    band or the grid, so placement never depends on which element the worker authors.
    ``view_hint`` is an explicit presentation the user requested (else ``None``).

    Example:
        WidgetSpec(id="widget-0", title="Total amount", sub_question="total amount",
                   role="metric")
    """

    id: str
    title: str
    sub_question: str
    role: WidgetRole
    view_hint: WidgetViewHint | None = None


@dataclass(frozen=True)
class WidgetResult:
    """A widget's executed result: its title, rows (for the ``/state`` patch), and SQL.

    Example:
        WidgetResult(widget_id="widget-0", title="Amount", result=QueryResult(...), sql="SELECT 1")
    """

    widget_id: str
    title: str
    result: QueryResult
    sql: str
