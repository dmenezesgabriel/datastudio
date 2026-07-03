"""Immutable value object for a single conversation turn."""

from dataclasses import dataclass
from typing import Literal

from chat.domain.value_objects.render_tree import RenderTree

MessageRole = Literal["user", "assistant"]


@dataclass(frozen=True)
class Message:
    """A single turn in a conversation.

    ``view`` is the renderable presentation tree for assistant turns; it is ``None``
    for user turns (which carry only the question text).

    Example:
        Message(role="user", content="How many events?", view=None)
    """

    role: MessageRole
    content: str
    view: RenderTree | None
