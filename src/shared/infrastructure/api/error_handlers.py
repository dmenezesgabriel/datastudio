"""Centralized translation of domain errors into HTTP responses.

The single edge that maps semantic :class:`~shared.domain.errors.DomainError` failures to
transport (status code + JSON body) and logs them with structured context — so domain and
application code stay ignorant of HTTP. Registered once by the composition root.

Only shared-kernel categories are named here (``NotFoundError``, ``InvariantViolationError``);
component subclasses (e.g. ``chat.domain.errors.ConversationNotFoundError``) are caught through
the base registration and their category via ``isinstance``, so this module never imports a
component — keeping ``shared`` free of any component dependency.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.domain.errors import DomainError, InvariantViolationError, NotFoundError
from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)

# Category -> HTTP status. Ordered most-specific first; anything else is a 400.
_STATUS_BY_CATEGORY: tuple[tuple[type[DomainError], int], ...] = (
    (NotFoundError, 404),
    (InvariantViolationError, 422),
)
_DEFAULT_STATUS = 400


def register_error_handlers(app: FastAPI) -> None:
    """Register the domain-error handler on the app (call once from the composition root).

    Example:
        app = FastAPI()
        register_error_handlers(app)
    """
    app.add_exception_handler(DomainError, _handle_domain_error)


async def _handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    """Log the failure and translate it to its category's HTTP status.

    Registered only for :class:`DomainError`, so ``exc`` is always one at runtime; the
    broader ``Exception`` annotation is what Starlette's handler signature requires.
    """
    status = _status_for(exc)
    _logger.warning(
        "domain.error",
        extra={"error": type(exc).__name__, "status": status, "path": request.url.path},
    )
    return JSONResponse(status_code=status, content={"detail": str(exc)})


def _status_for(exc: Exception) -> int:
    """Map a domain error to its HTTP status by category, defaulting to 400."""
    return next((s for cat, s in _STATUS_BY_CATEGORY if isinstance(exc, cat)), _DEFAULT_STATUS)
