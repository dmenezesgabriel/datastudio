"""LangGraph node: emit a text-only answer, skipping the SQL/widget pipeline.

The planner (:class:`~chat.infrastructure.graph.nodes.plan_widgets.PlanWidgets`)
classifies conversational/definitional/meta questions as ``answer_kind == "text"``
and drafts the reply into ``text_answer``; this node promotes it to the ``response``
channel. Kept as its own node (rather than letting the planner write ``response``)
so the streaming adapter can recognize the node and emit a ``NarrativeReady`` event —
producing a narrative-only RenderTree with no widgets.
"""

from typing import cast

from chat.infrastructure.graph.chat_state import ChatState

# When the planner routes here it has drafted a reply; this only guards a plan that
# set answer_kind="text" without content (never expected, but avoids a blank answer).
_EMPTY_ANSWER = "I'm not sure how to answer that. Could you rephrase your question?"


class AnswerText:
    """Node that finalizes the planner's text-only answer as the turn's response.

    Example:
        AnswerText()({"text_answer": "I can query and visualize your data."})
        # → {"response": "I can query and visualize your data."}
    """

    def __call__(self, state: ChatState) -> dict[str, str]:
        """Promote the planner's drafted text answer to the response channel."""
        text = cast(dict[str, object], state).get("text_answer")
        answer = text.strip() if isinstance(text, str) and text.strip() else _EMPTY_ANSWER
        return {"response": answer}
