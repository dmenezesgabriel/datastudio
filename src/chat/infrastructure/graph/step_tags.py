"""Run tags that attribute LLM token usage to a logical pipeline step.

The ``build_widget`` worker runs several LLM calls (generate_sql, repair_sql,
generate_widget_view) inside a single graph node, so node-level attribution cannot
separate them — and because workers run in parallel, a shared ``current_node`` can even
race. Tagging each call's runnable with ``step_tag(...)`` lets the token callback (and
any LangSmith/OpenTelemetry trace) attribute usage to the step by its own run id, not to
whichever node happened to be current.

Example:
    model = chat_model.with_structured_output(Out).with_config({"tags": [step_tag("generate_sql")]})
"""

from collections.abc import Sequence

_STEP_TAG_PREFIX = "step:"


def step_tag(step: str) -> str:
    """Build the run tag that marks LLM calls belonging to a logical step."""
    return f"{_STEP_TAG_PREFIX}{step}"


def step_from_tags(tags: Sequence[str] | None) -> str | None:
    """Return the step name carried by a run's tags, or None when unmarked.

    Example:
        step_from_tags(["step:repair_sql", "seq:step:1"])  # "repair_sql"
    """
    for tag in tags or ():
        if tag.startswith(_STEP_TAG_PREFIX):
            return tag[len(_STEP_TAG_PREFIX) :]
    return None
