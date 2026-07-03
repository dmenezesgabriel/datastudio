"""json-render specification value objects produced by the presentation stage.

These mirror the ``vercel-labs/json-render`` flat spec format (``{root, elements}``
where each element has ``type``/``props``/``children``). The backend assembles the
tree deterministically and the frontend ``<Renderer>`` validates and renders it, so
these prop shapes must stay in sync with the TypeScript Zod catalogue.
"""

from pydantic import BaseModel


class RenderElement(BaseModel):
    """A single node in a json-render tree.

    ``props`` is intentionally heterogeneous (it varies per catalogue component)
    and is the serialization boundary between this backend and the renderer.

    Example:
        RenderElement(type="KpiStat", props={"label": "Total", "value": "42"}, children=[])
    """

    type: str
    props: dict[str, object]
    children: list[str]


class RenderTree(BaseModel):
    """A flat json-render spec: a root element id, the element map, and optional state.

    ``state`` carries each widget's backend-authored ``{columns, rows}`` data keyed by
    widget id, resolved by the elements' ``$state`` bindings — so a persisted dashboard
    (charts/tables) can be re-rendered faithfully, not just its narrative. It is ``None``
    for narrative-only trees (the SQL-failure/CLI paths).

    Example:
        RenderTree(root="stack", elements={"stack": RenderElement(...)},
                   state={"widget-0": {"columns": ["n"], "rows": [{"n": 42}]}})
    """

    root: str
    elements: dict[str, RenderElement]
    state: dict[str, object] | None = None
