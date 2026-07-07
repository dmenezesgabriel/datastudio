"""LangGraph entry node: cheaply route a turn away from the data pipeline when it is chitchat.

The routing gate of the pipeline (the "Routing" agentic pattern: classify first with a
cheap call, then dispatch). It runs before any schema discovery — question + history only,
no database, no schema — so a greeting or thanks is answered directly instead of paying for
``list_tables`` (DB), ``select_tables`` (LLM), ``get_schema`` (DB) and ``plan_widgets`` (LLM)
just to reach the same text answer. It is deliberately conservative: only a confident
``chitchat`` classification short-circuits, and any ambiguity — including capability/meta
questions ('what can you do?', 'which tables exist?') — falls through to the full pipeline,
where the schema-aware ``plan_widgets`` still handles the ``text`` case. So the worst case is
exactly today's path and no data question is ever mistaken for small talk.
"""

from typing import Literal, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes._structured_output import invoke_structured

_SYSTEM_PROMPT = (
    "You are the intent gate for a business-intelligence assistant. Classify ONLY the "
    "current turn, then stop.\n"
    "KIND:\n"
    "- 'chitchat' — the turn needs no data and no knowledge of the schema to answer well: a "
    "greeting, a thanks, an acknowledgement, or small talk. Write a brief, friendly reply in "
    "`reply`.\n"
    "- 'data' — anything else: a question about the data, OR a capability/meta question "
    "('what can you do?', 'which tables are there?') whose best answer depends on the actual "
    "schema. Leave `reply` empty; a later, schema-aware step will handle it.\n"
    "When in doubt, choose 'data'. It is far worse to treat a real question as small talk "
    "than to route a greeting through the full pipeline. Earlier turns, when present, are "
    "context: a terse follow-up like 'and by region?' is 'data', not chitchat."
)


class _IntentDecision(BaseModel):
    # Defaults bias to the safe path: an omitted/partial decision degrades to the full
    # pipeline rather than swallowing a real question as chitchat.
    kind: Literal["chitchat", "data"] = "data"
    reply: str = ""


class RouteIntent:
    """Node that classifies a turn as chitchat (direct reply) or data (enter the pipeline).

    Example:
        node = RouteIntent(chat_model)
        node({"question": "hello", "history": []})
        # → {"answer_kind": "text", "text_answer": "Hi! Ask me about your data."}
        node({"question": "events by category", "history": []})
        # → {}  (falls through to list_tables → ... → plan_widgets)
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        """Wire the chat model as a structured-output runnable."""
        self._model: Runnable[LanguageModelInput, _IntentDecision] = cast(
            Runnable[LanguageModelInput, _IntentDecision],
            chat_model.with_structured_output(_IntentDecision),
        )

    def __call__(self, state: ChatState) -> dict[str, object]:
        """Short-circuit confident chitchat to a text answer; otherwise enter the pipeline."""
        decision = invoke_structured(self._model, self._messages(state), "route_intent")
        if decision is not None and _is_chitchat(decision):
            return {"answer_kind": "text", "text_answer": decision.reply.strip()}
        # Data, an empty chitchat reply, or malformed output all fall through to the pipeline.
        return {}

    def _messages(self, state: ChatState) -> list[BaseMessage]:
        """Build ``[System, *history, Human]`` — question and prior turns only, no schema."""
        return [
            SystemMessage(content=_SYSTEM_PROMPT),
            *state["history"],
            HumanMessage(content=state["question"]),
        ]


def _is_chitchat(decision: _IntentDecision) -> bool:
    """True when the gate confidently chose a direct reply with non-empty content."""
    return decision.kind == "chitchat" and bool(decision.reply.strip())
