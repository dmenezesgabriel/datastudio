"""FastAPI application factory for the chat web UI."""

import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from langchain_core.language_models import BaseChatModel

from chat.application.use_cases.stream_message import StreamMessage
from chat.infrastructure.api.chat_router import ChatRouter
from chat.infrastructure.graph.litellm_language_model import LiteLLMLanguageModel
from chat.infrastructure.graph.text2sql_engine_adapter import Text2SqlEngineAdapter
from chat.infrastructure.graph.text2sql_graph import build_text2sql_graph
from chat.infrastructure.persistence.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from shared.infrastructure.config.settings import AppSettings
from shared.infrastructure.logging.logger_factory import get_logger
from shared.infrastructure.logging.logging_config import configure_logging
from shared.infrastructure.sql_engine.duckdb.duckdb_sql_engine import DuckDbSqlEngine

_logger = get_logger(__name__)


def build_stream_message(settings: AppSettings) -> StreamMessage:
    """Wire the graph, engine adapter, in-memory memory, and use case from settings.

    Example:
        use_case = build_stream_message(AppSettings())
    """
    chat_model = _build_chat_model(settings, settings.language_model_name)
    format_chat_model = _build_chat_model(settings, settings.format_model_name)
    graph = build_text2sql_graph(
        chat_model,
        DuckDbSqlEngine(settings.duckdb_path),
        format_chat_model=format_chat_model,
        api_base=settings.openai_base_url,
    )
    engine = Text2SqlEngineAdapter(graph, timeout_s=settings.query_timeout_s)
    return StreamMessage(InMemoryConversationRepository(), engine)


def create_app() -> FastAPI:
    """Build the FastAPI app: register the chat API, then mount the built frontend.

    Example:
        app = create_app()
    """
    settings = AppSettings()  # type: ignore[call-arg]
    configure_logging(settings.log_level)
    # LiteLLM emits INFO for every LLM call — reduces noise in our structured stream.
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    app = FastAPI(title="datastudio chat")
    app.include_router(ChatRouter(build_stream_message(settings)).router)
    _mount_frontend(app, settings.frontend_dist_path)
    return app


def run() -> None:
    """Serve the app with uvicorn (entry point for the datastudio-api script)."""
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)


def _build_chat_model(settings: AppSettings, model_name: str) -> BaseChatModel:
    """Build a chat model from settings for the given model name."""
    return LiteLLMLanguageModel(
        model_name=model_name,
        temperature=settings.language_model_temperature,
        api_key=settings.openai_api_key,
        api_base=settings.openai_base_url,
    ).get_chat_model()


def _mount_frontend(app: FastAPI, dist_path: str) -> None:
    """Serve the built SPA at / when the dist directory exists; otherwise API-only."""
    if not Path(dist_path).is_dir():
        _logger.warning("frontend dist not found at %s; serving API only", dist_path)
        return
    app.mount("/", StaticFiles(directory=dist_path, html=True))
