"""Shared-kernel domain error hierarchy.

Semantic failures raised by domain and application code. They are transport-neutral
by design — the domain ring must not know about HTTP — so the mapping from category to
status code lives in the infrastructure edge (``shared.infrastructure.api.error_handlers``).

Components extend these categories with concrete, resource-named exceptions in their own
``<component>/domain/errors.py`` (e.g. ``chat.domain.errors.ConversationNotFound``); the
shared kernel holds only the categories, never component vocabulary.

Example:
    from shared.domain.errors import NotFoundError

    class ConversationNotFound(NotFoundError):
        ...
"""


class DomainError(Exception):
    """Base for semantic domain/application failures.

    Driving adapters catch this at the edge, log it, and translate it into a transport
    error (an HTTP status, a CLI message). Domain and application code raise subclasses
    of it instead of leaking framework exceptions outward.
    """


class InvariantViolationError(DomainError):
    """A value object or entity invariant was broken (e.g. a required field is empty)."""


class NotFoundError(DomainError):
    """A requested resource does not exist for the caller (absent, or not theirs)."""
