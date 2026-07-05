"""Composition root: wires each component's HTTP adapter into one backend.

The app's bootstrap / dependency container — the single module allowed to know
about every component. Components stay self-contained (each exposes a
``build_<component>_api`` factory); the decision of which to wire together — one
backend, or one component per container / FaaS — lives here in ``_COMPONENT_APIS``.

Example:
    app = create_app()  # or `uvicorn bootstrap:create_app --factory`
"""

import logging
from collections.abc import Callable

import uvicorn
from fastapi import APIRouter, FastAPI

from chat.infrastructure.api.chat_api import build_chat_api
from shared.infrastructure.config.settings import AppSettings
from shared.infrastructure.logging.logging_config import configure_logging

# The seam every component's HTTP adapter implements: settings in, its routers out.
ComponentApiFactory = Callable[[AppSettings], list[APIRouter]]

# The wiring decision: which component APIs make up this backend. Add a component
# by appending its factory; a single-component deploy wires a one-element tuple.
_COMPONENT_APIS: tuple[ComponentApiFactory, ...] = (build_chat_api,)


def create_app() -> FastAPI:
    """Assemble the backend: configure the runtime, then mount every component's API.

    Example:
        app = create_app()
    """
    settings = AppSettings()  # type: ignore[call-arg]
    _configure_runtime(settings)
    app = FastAPI(title="datastudio")
    for build_api in _COMPONENT_APIS:
        for router in build_api(settings):
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
