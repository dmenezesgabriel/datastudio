"""Use case: send a user message and stream the assistant's dashboard answer."""

from chat.application.ports.conversation_repository import ConversationRepository
from chat.application.ports.text2sql_port import Text2SqlPort
from chat.application.ports.turn_view_builder import TurnViewBuilder
from chat.application.use_cases.save_artifact import SaveArtifact
from chat.domain.entities.conversation import Conversation
from chat.domain.services.dashboard_widgets import artifact_drafts
from chat.domain.value_objects.render_tree import RenderTree
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
    the stream drains—records the assistant turn (the overall summary), persists the
    conversation, and auto-saves the produced dashboard and each of its widgets as
    artifacts (so nothing generated in chat is lost). Dependencies are injected so the
    use case stays infra-free.

    Example:
        use_case = StreamMessage(repository, engine, view_builder, save_artifact)
        async for event in use_case.execute("guest", "c-1", "Overview"):
            ...
    """

    def __init__(
        self,
        repository: ConversationRepository,
        engine: Text2SqlPort,
        view_builder: TurnViewBuilder,
        save_artifact: SaveArtifact,
    ) -> None:
        """Wire the conversation repository, the engine, the view builder, and artifact save.

        The use case does no logging — that is a driving-adapter concern. The API edge
        logs the request lifecycle so the application layer stays transport-agnostic.
        """
        self._repository = repository
        self._engine = engine
        self._view_builder = view_builder
        self._save_artifact = save_artifact

    async def execute(self, owner_id: str, conversation_id: str, question: str) -> TypedChatStream:
        """Record the question, stream the answer, then persist both turns.

        Scoped to ``owner_id``: an existing conversation is only continued when it
        belongs to this caller — otherwise a fresh one is started under them, so a
        caller can never write into another user's thread. The short-term memory
        window is read *before* the current question is appended, so ``question``
        is passed once (as the current turn) and never duplicated inside history.
        """
        existing = self._repository.get(conversation_id, owner_id)
        conversation = existing or Conversation.new(conversation_id, owner_id)
        history = conversation.recent_messages(_MEMORY_WINDOW_MESSAGES)  # prior turns only
        conversation.append_user_message(question)
        narrative = ""
        turn_events: list[ChatStreamEvent] = []
        async for event in self._engine.stream(question, history):
            if isinstance(event, NarrativeReady):
                narrative = event.text
            if not isinstance(event, ProgressStep):
                turn_events.append(event)  # keep the payload; progress is transient chrome
            yield event
        view = self._record_assistant_turn(conversation, narrative, turn_events)
        self._repository.save(conversation)
        if view is not None:
            self._auto_save_artifacts(owner_id, conversation_id, question, view)

    def _record_assistant_turn(
        self, conversation: Conversation, narrative: str, events: list[ChatStreamEvent]
    ) -> RenderTree | None:
        """Append the assistant turn, persisting the full dashboard so it re-renders on reopen.

        Returns the built view (or ``None`` when the stream produced no summary) so the
        caller can promote it — and its widgets — into artifacts.
        """
        if not narrative:
            return None  # stream ended without a summary (abnormal) — nothing to remember
        view = self._view_builder.build(events)
        result = Text2SqlResult(narrative=narrative, view=view)
        conversation.append_assistant_message(result)
        return view

    def _auto_save_artifacts(
        self, owner_id: str, conversation_id: str, question: str, view: RenderTree
    ) -> None:
        """Persist the produced dashboard and each of its widgets as their own artifacts.

        A text-only answer yields no drafts (nothing to persist); a dashboard yields the
        whole dashboard plus one single-widget artifact per widget.
        """
        for draft in artifact_drafts(question, view):
            self._save_artifact.execute(
                owner_id, draft.title, draft.spec, source_conversation_id=conversation_id
            )
