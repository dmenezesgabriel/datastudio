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
    """A flat json-render spec: a root element id plus the element map.

    Example:
        RenderTree(root="stack", elements={"stack": RenderElement(...)})
    """

    root: str
    elements: dict[str, RenderElement]
