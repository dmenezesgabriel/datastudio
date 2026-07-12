"""Type aliases shared across identity's infrastructure adapters."""

from collections.abc import Awaitable, Callable

from identity.domain.value_objects.principal import Principal

# A FastAPI dependency yielding the full current :class:`Principal`. Its
# parameters are supplied by FastAPI (the ``Authorization`` header); used only
# via ``Depends(resolve)``. Shared by ``current_user`` (which builds it),
# ``me_router`` (which consumes it), and ``identity_api`` (which wires it).
ResolvePrincipal = Callable[..., Awaitable[Principal]]
