"""Use case: send a user message and produce the assistant's answer turn."""

from chat.application.ports.conversation_repository import ConversationRepository
from chat.application.ports.text2sql_port import Text2SqlPort
from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.text2sql_result import Text2SqlResult
from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)


class SendMessage:
    """Orchestrates one chat round-trip over the conversation memory and engine.

    Loads (or starts) the conversation, records the user question, answers it via
    the text2sql engine, records the assistant turn for memory, persists, and
    returns the engine result (response, SQL, and render tree). Dependencies are
    injected so the use case stays free of infrastructure detail.

    Example:
        use_case = SendMessage(repository, engine)
        result = use_case.execute("c-1", "How many orders?")
    """

    def __init__(self, repository: ConversationRepository, engine: Text2SqlPort) -> None:
        """Wire the conversation repository and text2sql engine."""
        self._repository = repository
        self._engine = engine

    def execute(self, conversation_id: str, question: str) -> Text2SqlResult:
        """Record the question, answer it, persist both turns, return the result."""
        existing = self._repository.get(conversation_id)
        _logger.info(
            "send_message.start",
            extra={"conversation_id": conversation_id, "is_new": existing is None},
        )
        conversation = existing or Conversation.new(conversation_id)
        conversation.append_user_message(question)
        result = self._engine.answer(question)
        conversation.append_assistant_message(result)
        self._repository.save(conversation)
        _logger.info("send_message.complete", extra={"conversation_id": conversation_id})
        return result
