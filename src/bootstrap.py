"""Composition root: wires each component's HTTP adapter into one backend.

The app's bootstrap / dependency container — the single module allowed to know
about every component. Components stay self-contained (each exposes a
``build_<component>_api`` factory); the decision of how to wire them together —
including cross-component dependencies like feature contexts consuming identity's
current-user resolver — lives here and nowhere else.

Example:
    app = create_app()  # or `uvicorn bootstrap:create_app --factory`
"""

import logging

import uvicorn
from fastapi import APIRouter, FastAPI

from chat.infrastructure.api.chat_api import build_chat_api
from identity.infrastructure.api.identity_api import build_identity_api
from shared.infrastructure.api.error_handlers import register_error_handlers
from shared.infrastructure.config.settings import AppSettings
from shared.infrastructure.logging.logging_config import configure_logging


def create_app() -> FastAPI:
    """Assemble the backend: configure the runtime, then mount every component's API.

    Identity is built first so its current-user resolver can be injected into the
    feature components (chat) that scope their data by owner.

    Example:
        app = create_app()
    """
    settings = AppSettings()  # type: ignore[call-arg]
    _configure_runtime(settings)
    app = FastAPI(title="datastudio")
    register_error_handlers(app)  # domain errors -> HTTP, in one place
    identity = build_identity_api(settings)
    routers: list[APIRouter] = [
        *identity.routers,
        *build_chat_api(settings, identity.resolve_current_user),
    ]
    for router in routers:
        app.include_router(router)
    return app


def run() -> None:
    """Serve the backend with uvicorn (entry point for the datastudio-api script)."""
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)


def _configure_runtime(settings: AppSettings) -> None:
    """Process-wide setup shared by all components (logging, noisy-lib levels)."""
    configure_logging(settings.log_level)
    # LiteLLM emits INFO for every LLM call — reduces noise in our structured stream.
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
