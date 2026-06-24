"""Shared infrastructure-layer type aliases for the chat component.

Following Python's `TypedDict` naming convention, aliases defined here use the
`Typed` prefix to signal that a generic type has been narrowed to the concrete
types used by this component.
"""

from langgraph.graph.state import CompiledStateGraph  # pyright: ignore[reportMissingTypeStubs]

from chat.domain.value_objects.chat_state import ChatState

TypedChatGraph = CompiledStateGraph[ChatState, None, ChatState, ChatState]
"""A compiled LangGraph state-machine whose state, input, and output are all `ChatState`.

The four type parameters map to:
  - ``StateT``   → ``ChatState``   (the shared graph state)
  - ``ContextT`` → ``None``        (no run-scoped context)
  - ``InputT``   → ``ChatState``   (what ``invoke()`` accepts)
  - ``OutputT``  → ``ChatState``   (what ``invoke()`` returns)
"""
