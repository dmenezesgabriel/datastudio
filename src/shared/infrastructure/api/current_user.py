"""Cross-component HTTP seam: resolve the current request's owning user id.

The type a feature context (today: ``chat``) depends on to scope its data by
owner, provided by ``identity``'s infrastructure and wired at ``bootstrap.py``.

It lives in the *infrastructure* ring on purpose: resolving a caller from an HTTP
request is an HTTP concern. The application/domain layers take a plain
``owner_id: str`` and never see this type, so they stay framework-free — no
FastAPI ``Depends`` shape leaks inward.
"""

from collections.abc import Awaitable, Callable

# A FastAPI dependency yielding the current request's owner ``user_id``. Its
# parameters are supplied by FastAPI (e.g. the ``Authorization`` header), so the
# signature is left open — callers use it only via ``Depends(resolve)``.
ResolveOwnerId = Callable[..., Awaitable[str]]
