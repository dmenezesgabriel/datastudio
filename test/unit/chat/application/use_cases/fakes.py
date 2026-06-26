from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.text2sql_result import Text2SqlResult


class FakeConversationRepository:
    """In-test conversation store recording saves keyed by id."""

    def __init__(self) -> None:
        self.saved: dict[str, Conversation] = {}

    def get(self, conversation_id: str) -> Conversation | None:
        return self.saved.get(conversation_id)

    def save(self, conversation: Conversation) -> None:
        self.saved[conversation.conversation_id] = conversation


class FakeText2SqlEngine:
    """Engine returning a fixed result and recording questions asked."""

    def __init__(self, result: Text2SqlResult) -> None:
        self._result = result
        self.questions: list[str] = []

    def answer(self, question: str) -> Text2SqlResult:
        self.questions.append(question)
        return self._result


def make_result(response: str = "ans") -> Text2SqlResult:
    """Build a minimal Text2SqlResult for use-case tests."""
    view = RenderTree(
        root="root",
        elements={"root": RenderElement(type="Stack", props={}, children=[])},
    )
    return Text2SqlResult(response=response, sql_query="SELECT 1", view=view)
