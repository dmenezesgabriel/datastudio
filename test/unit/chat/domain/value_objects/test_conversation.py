from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.text2sql_result import Text2SqlResult


def _view() -> RenderTree:
    return RenderTree(
        root="root",
        elements={"root": RenderElement(type="Stack", props={}, children=[])},
    )


def _result(response: str = "42") -> Text2SqlResult:
    return Text2SqlResult(response=response, sql_query="SELECT 1", view=_view())


class TestConversationAppendUserMessage:
    def test_appends_user_message_with_correct_role(self) -> None:
        # arrange
        conv = Conversation.new("c-1")
        # act
        msg = conv.append_user_message("How many orders?")
        # assert
        assert msg.role == "user"
        assert msg.content == "How many orders?"
        assert msg.view is None

    def test_user_message_appears_in_messages(self) -> None:
        conv = Conversation.new("c-1")
        conv.append_user_message("q")
        assert len(conv.messages) == 1


class TestConversationAppendAssistantMessage:
    def test_propagates_view_from_result(self) -> None:
        # arrange — view propagation: changing view=result.view to view=None must be caught
        conv = Conversation.new("c-1")
        view = _view()
        result = Text2SqlResult(response="42", sql_query="SELECT 1", view=view)
        # act
        msg = conv.append_assistant_message(result)
        # assert
        assert msg.view is view

    def test_appends_assistant_message_with_correct_role_and_content(self) -> None:
        conv = Conversation.new("c-1")
        msg = conv.append_assistant_message(_result("There are 42 orders."))
        assert msg.role == "assistant"
        assert msg.content == "There are 42 orders."

    def test_assistant_message_appears_in_messages(self) -> None:
        conv = Conversation.new("c-1")
        conv.append_assistant_message(_result())
        assert len(conv.messages) == 1
