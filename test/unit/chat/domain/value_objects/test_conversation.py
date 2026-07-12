from chat.domain.entities.conversation import Conversation
from chat.domain.value_objects.render_tree import RenderElement, RenderTree
from chat.domain.value_objects.text2sql_result import Text2SqlResult


def _view() -> RenderTree:
    return RenderTree(
        root="root",
        elements={"root": RenderElement(type="Stack", props={}, children=[])},
    )


def _result(response: str = "42") -> Text2SqlResult:
    return Text2SqlResult(narrative=response, view=_view())


class TestConversationOwner:
    def test_new_stamps_the_owning_user(self) -> None:
        # the owner rides on the entity so the repository can scope reads by it
        assert Conversation.new("c-1", "alice").owner_id == "alice"


class TestConversationAppendUserMessage:
    def test_appends_user_message_with_correct_role(self) -> None:
        # arrange
        conv = Conversation.new("c-1", "u-1")
        # act
        msg = conv.append_user_message("How many orders?")
        # assert
        assert msg.role == "user"
        assert msg.content == "How many orders?"
        assert msg.view is None

    def test_user_message_appears_in_messages(self) -> None:
        conv = Conversation.new("c-1", "u-1")
        conv.append_user_message("q")
        assert len(conv.messages) == 1


class TestConversationAppendAssistantMessage:
    def test_propagates_view_from_result(self) -> None:
        # arrange — view propagation: changing view=result.view to view=None must be caught
        conv = Conversation.new("c-1", "u-1")
        view = _view()
        result = Text2SqlResult(narrative="42", view=view)
        # act
        msg = conv.append_assistant_message(result)
        # assert
        assert msg.view is view

    def test_appends_assistant_message_with_correct_role_and_content(self) -> None:
        conv = Conversation.new("c-1", "u-1")
        msg = conv.append_assistant_message(_result("There are 42 orders."))
        assert msg.role == "assistant"
        assert msg.content == "There are 42 orders."

    def test_assistant_message_appears_in_messages(self) -> None:
        conv = Conversation.new("c-1", "u-1")
        conv.append_assistant_message(_result())
        assert len(conv.messages) == 1


class TestConversationTitle:
    def test_title_is_the_first_user_question(self) -> None:
        # arrange
        conv = Conversation.new("c-1", "u-1")
        conv.append_user_message("How many orders were there?")
        conv.append_assistant_message(_result())
        conv.append_user_message("And by month?")
        # act / assert — the first question labels the thread
        assert conv.title() == "How many orders were there?"

    def test_title_defaults_when_no_user_message(self) -> None:
        assert Conversation.new("c-1", "u-1").title() == "New chat"

    def test_title_truncates_a_long_question(self) -> None:
        # arrange — a question longer than the 60-char label budget
        conv = Conversation.new("c-1", "u-1")
        conv.append_user_message("word " * 30)
        # act
        title = conv.title()
        # assert — clipped to the budget and ellipsised
        assert len(title) <= 60
        assert title.endswith("…")


class TestConversationRecentMessages:
    def test_returns_the_last_n_turns(self) -> None:
        # arrange — six turns; the window keeps only the most recent four
        conv = Conversation.new("c-1", "u-1")
        for i in range(3):
            conv.append_user_message(f"q{i}")
            conv.append_assistant_message(_result(f"a{i}"))
        # act
        window = conv.recent_messages(4)
        # assert — the tail, in order
        assert [m.content for m in window] == ["q1", "a1", "q2", "a2"]

    def test_returns_all_when_fewer_than_window(self) -> None:
        conv = Conversation.new("c-1", "u-1")
        conv.append_user_message("only")
        assert [m.content for m in conv.recent_messages(10)] == ["only"]

    def test_non_positive_window_yields_no_memory(self) -> None:
        conv = Conversation.new("c-1", "u-1")
        conv.append_user_message("q")
        assert conv.recent_messages(0) == []
