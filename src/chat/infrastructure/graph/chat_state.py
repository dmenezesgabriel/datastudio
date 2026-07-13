"""Chat state TypedDict shared across all LangGraph nodes."""

from operator import add
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage

from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.widget import WidgetResult, WidgetSpec
from shared.domain.value_objects.query_result import QueryResult


class ChatState(TypedDict):
    """Graph state shared across all nodes in the chat LangGraph.

    The flow discovers the schema once, plans 1..N widgets, then fans out one
    parallel ``build_widget`` worker per widget (via ``Send``). The two
    ``Annotated[..., add]`` channels let those concurrent workers append their
    outputs without clobbering each other; ``widget``/``sql``/``query_result``/
    ``sql_error``/``repair_attempts`` are the per-worker working fields (carried on
    the local state a worker drives, not across the main graph).

    ``NotRequired`` fields are absent until the node that sets them has run.
    """

    request_id: NotRequired[str]  # UUID set by the engine adapter; absent in eval/test runs
    question: str
    # Prior-turn conversation context (short-term memory) the LLM nodes read as they
    # build their message list: ``[System, *history, Human]``. Required and empty on
    # the first turn; the adapter fills it from the Conversation repository each turn.
    history: list[BaseMessage]
    tables: list[str]
    schema: str
    # plan_widgets classifies the turn: "text" → a direct answer (answer_text node),
    # "data" → a 1..N-widget dashboard (fan-out). Absent until plan_widgets has run.
    answer_kind: NotRequired[str]
    text_answer: NotRequired[str]  # planner-drafted reply on the text path; promoted by answer_text
    widget_specs: NotRequired[list[WidgetSpec]]  # set by plan_widgets; read by the fan-out edge
    widget: NotRequired[WidgetSpec]  # the single widget a build_widget worker is building
    sql: NotRequired[str]  # per-widget working fields (local to a build_widget worker)
    sql_error: NotRequired[str]
    repair_attempts: NotRequired[int]
    query_result: NotRequired[QueryResult]
    widget_patch_lines: Annotated[list[str], add]  # each worker appends its SpecStream patch lines
    widget_results: Annotated[list[WidgetResult], add]  # each worker appends its executed result
    narrative: str  # the overall narrative, set by compose_narrative
    # Edit-graph-only fields (absent on the build flow): an edit reopens a saved dashboard,
    # so ``prior_spec`` seeds the current dashboard as context and ``classify_edit`` routes the
    # turn — ``restyle`` (patch existing elements, no SQL) vs ``reanalyze`` (rebuild one widget
    # via the SQL worker, reusing ``widget``/``question`` above with ``target_widget_id``).
    instruction: NotRequired[str]  # the user's edit request (edit graph)
    prior_spec: NotRequired[RenderTree]  # the artifact's current dashboard spec, seeded for edits
    edit_mode: NotRequired[str]  # "restyle" | "reanalyze"; set by classify_edit
    target_widget_id: NotRequired[str]  # widget id a reanalyze rebuilds (existing or minted)
