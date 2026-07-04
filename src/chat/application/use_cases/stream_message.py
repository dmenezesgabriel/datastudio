"""Use case: send a user message and stream the assistant's dashboard answer."""

import logging

from chat.application.ports.conversation_repository import ConversationRepository
from chat.application.ports.text2sql_port import Text2SqlPort
from chat.application.ports.turn_view_builder import TurnViewBuilder
from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.stream_event import (
    ChatStreamEvent,
    NarrativeReady,
    ProgressStep,
    TypedChatStream,
)
from chat.domain.value_objects.text2sql_result import Text2SqlResult

# Short-term memory window: how many prior turns are injected as context each turn.
# ~5 exchanges — enough to resolve follow-ups while keeping prompt size flat.
_MEMORY_WINDOW_MESSAGES = 10


class StreamMessage:
    """Orchestrates one streamed chat round-trip over conversation memory and the engine.

    Records the user question, forwards every engine event to the caller (the widget
    data flows in-stream as ``/state`` patches, so no data is stashed here), and—once
    the stream drains—records the assistant turn (the overall summary) and persists.
    Dependencies are injected so the use case stays infra-free.

    Example:
        use_case = StreamMessage(repository, engine, view_builder, logger)
        async for event in use_case.execute("c-1", "Overview"):
            ...
    """

    def __init__(
        self,
        repository: ConversationRepository,
        engine: Text2SqlPort,
        view_builder: TurnViewBuilder,
        logger: logging.Logger,
    ) -> None:
        """Wire the conversation repository, the text2sql engine, view builder, and logger.

        ``logger`` is injected (not built from an infrastructure factory) so the
        application layer depends only on the stdlib ``logging`` abstraction — the
        composition root supplies the configured structured logger.
        """
        self._repository = repository
        self._engine = engine
        self._view_builder = view_builder
        self._logger = logger

    async def execute(self, conversation_id: str, question: str) -> TypedChatStream:
        """Record the question, stream the answer, then persist both turns.

        The short-term memory window is read *before* the current question is
        appended, so ``question`` is passed once (as the current turn) and never
        duplicated inside the injected history.
        """
        existing = self._repository.get(conversation_id)
        conversation = existing or Conversation.new(conversation_id)
        history = conversation.recent_messages(_MEMORY_WINDOW_MESSAGES)  # prior turns only
        self._logger.info(
            "stream_message.start",
            extra={
                "conversation_id": conversation_id,
                "is_new": existing is None,
                "history_message_count": len(history),
            },
        )
        conversation.append_user_message(question)
        narrative = ""
        turn_events: list[ChatStreamEvent] = []
        async for event in self._engine.stream(question, history):
            if isinstance(event, NarrativeReady):
                narrative = event.text
            if not isinstance(event, ProgressStep):
                turn_events.append(event)  # keep the payload; progress is transient chrome
            yield event
        self._record_assistant_turn(conversation, narrative, turn_events)
        self._repository.save(conversation)
        self._logger.info("stream_message.complete", extra={"conversation_id": conversation_id})

    def _record_assistant_turn(
        self, conversation: Conversation, narrative: str, events: list[ChatStreamEvent]
    ) -> None:
        """Append the assistant turn, persisting the full dashboard so it re-renders on reopen."""
        if not narrative:
            return  # stream ended without a summary (abnormal) — nothing to remember
        view = self._view_builder.build(events)
        result = Text2SqlResult(narrative=narrative, view=view)
        conversation.append_assistant_message(result)
