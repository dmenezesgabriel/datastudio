"""Value object: a lightweight conversation descriptor for the sidebar thread list."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationSummary:
    """A conversation's at-a-glance metadata, enough to list and reopen it.

    ``title`` is the recognisable label (the first question); ``updated_at`` is a Unix
    timestamp used to order the sidebar most-recent-first.

    Example:
        ConversationSummary(conversation_id="c-1", title="Events by category",
                            message_count=4, updated_at=1751500000.0)
    """

    conversation_id: str
    title: str
    message_count: int
    updated_at: float
