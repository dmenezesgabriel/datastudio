"""The F-layout contract a dashboard RenderTree is assembled against.

One home for the element ids the backend seeds, routes widgets into, and describes to the
view-editing model. These names are a *contract between modules that never call each other*:
the serializer seeds the regions, the view-authoring node appends widgets to them, the
persistence layer identifies widgets by their frame, and the restyle prompt names all of them
in prose to the LLM. Re-declaring the strings per module let a rename compile and pass tests
while the prompt quietly went on describing the old layout — hence this module.
"""

KPI_REGION = "kpi-row"
"""The headline band, first under the root: one KpiStat card per ``metric`` widget."""

GRID_REGION = "grid"
"""The charts/tables grid below the KPI band, holding every ``analysis`` widget."""

FRAME_SUFFIX = "-frame"
"""Suffix of the ``WidgetFrame`` element that wraps a widget's visualization leaf."""


def frame_id(widget_id: str) -> str:
    """The id of the WidgetFrame element wrapping a widget's visualization leaf.

    Example:
        frame_id("widget-0")  # "widget-0-frame"
    """
    return f"{widget_id}{FRAME_SUFFIX}"
