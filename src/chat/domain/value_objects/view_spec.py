"""Compact visualization recommendation produced by the recommend_view node.

The LLM returns only *intent* — which chart kinds to draw and which result columns
play which role — never the data itself. Deterministic assembly (render_tree_builder)
injects the real ``QueryResult`` rows, so query numbers never pass through the model.
"""

from typing import Literal

from pydantic import BaseModel

ChartKind = Literal["bar", "line", "pie"]


class ChartSpec(BaseModel):
    """A single recommended chart, referencing result columns by name.

    Example:
        ChartSpec(kind="bar", title="Revenue by month",
                  label_column="month", value_columns=["revenue"])
    """

    kind: ChartKind
    title: str
    label_column: str
    value_columns: list[str]


class KpiSpec(BaseModel):
    """A single headline metric taken from the first row of ``value_column``.

    Example:
        KpiSpec(label="Total orders", value_column="order_count")
    """

    label: str
    value_column: str


class ViewSpec(BaseModel):
    """The full presentation recommendation for one answered question.

    Example:
        ViewSpec(kpis=[KpiSpec(...)], charts=[ChartSpec(...)], show_table=True)
    """

    kpis: list[KpiSpec]
    charts: list[ChartSpec]
    show_table: bool
