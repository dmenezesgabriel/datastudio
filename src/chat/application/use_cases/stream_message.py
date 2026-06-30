"""Use case: send a user message and stream the assistant's dashboard answer."""

from chat.application.ports.conversation_repository import ConversationRepository
from chat.application.ports.text2sql_port import Text2SqlPort
from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.stream_event import NarrativeReady, TypedChatStream
from chat.domain.value_objects.text2sql_result import Text2SqlResult
from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)


class StreamMessage:
    """Orchestrates one streamed chat round-trip over conversation memory and the engine.

    Records the user question, forwards every engine event to the caller (the widget
    data flows in-stream as ``/state`` patches, so no data is stashed here), and—once
    the stream drains—records the assistant turn (the overall summary) and persists.
    Dependencies are injected so the use case stays infra-free.

    Example:
        use_case = StreamMessage(repository, engine)
        async for event in use_case.execute("c-1", "Sales overview"):
            ...
    """

    def __init__(self, repository: ConversationRepository, engine: Text2SqlPort) -> None:
        """Wire the conversation repository and the text2sql engine."""
        self._repository = repository
        self._engine = engine

    async def execute(self, conversation_id: str, question: str) -> TypedChatStream:
        """Record the question, stream the answer, then persist both turns."""
        existing = self._repository.get(conversation_id)
        _logger.info(
            "stream_message.start",
            extra={"conversation_id": conversation_id, "is_new": existing is None},
        )
        conversation = existing or Conversation.new(conversation_id)
        conversation.append_user_message(question)
        response = ""
        async for event in self._engine.stream(question):
            if isinstance(event, NarrativeReady):
                response = event.text
            yield event
        self._record_assistant_turn(conversation, response)
        self._repository.save(conversation)
        _logger.info("stream_message.complete", extra={"conversation_id": conversation_id})

    def _record_assistant_turn(self, conversation: Conversation, response: str) -> None:
        """Append the assistant turn for memory (narrative-only view; never re-rendered)."""
        if not response:
            return  # stream ended without a summary (abnormal) — nothing to remember
        result = Text2SqlResult(response=response, sql_query="", view=_narrative_view(response))
        conversation.append_assistant_message(result)


def _narrative_view(response: str) -> RenderTree:
    """A minimal narrative-only render tree for the persisted assistant turn."""
    return RenderTree(
        root="root",
        elements={
            "root": RenderElement(type="Stack", props={}, children=["narrative"]),
            "narrative": RenderElement(type="Markdown", props={"text": response}, children=[]),
        },
    )
