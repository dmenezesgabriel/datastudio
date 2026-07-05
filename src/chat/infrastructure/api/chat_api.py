"""HTTP assembly seam for the chat component.

Self-contained wiring for chat's FastAPI surface: ``build_chat_api`` composes the
object graph from settings, while ``build_chat_routers`` does the pure assembly
over injected collaborators. The composition root (``bootstrap.py``) mounts these
routers; keeping the seam here lets chat be deployed alone or alongside others.
"""

from fastapi import APIRouter
from langchain_core.language_models import BaseChatModel

from chat.application.ports.conversation_repository import ConversationRepository
from chat.application.use_cases.stream_message import StreamMessage
from chat.infrastructure.api.chat_router import ChatRouter
from chat.infrastructure.api.conversations_router import ConversationsRouter
from chat.infrastructure.api.dashboard_view_builder import DashboardViewBuilder
from chat.infrastructure.graph.litellm_language_model import LiteLLMLanguageModel
from chat.infrastructure.graph.text2sql_engine_adapter import Text2SqlEngineAdapter
from chat.infrastructure.graph.text2sql_graph import build_text2sql_graph
from chat.infrastructure.persistence.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from shared.infrastructure.config.settings import AppSettings
from shared.infrastructure.logging.logger_factory import get_logger
from shared.infrastructure.sql_engine.duckdb.duckdb_sql_engine import DuckDbSqlEngine


def build_chat_routers(
    stream_message: StreamMessage, repository: ConversationRepository
) -> list[APIRouter]:
    """Assemble chat's routers over a shared conversation store (abstractions injected).

    One store feeds both the write-side ``ChatRouter`` (via the use case) and the
    read-side ``ConversationsRouter`` — otherwise the sidebar sees an empty one.

    Example:
        routers = build_chat_routers(stream_message, repository)
        for router in routers:
            app.include_router(router)
    """
    return [ChatRouter(stream_message).router, ConversationsRouter(repository).router]


def build_chat_api(settings: AppSettings) -> list[APIRouter]:
    """Compose chat's HTTP surface from settings; self-contained for standalone deploy.

    Example:
        for router in build_chat_api(AppSettings()):
            app.include_router(router)
    """
    repository = InMemoryConversationRepository()  # one shared store, by construction
    return build_chat_routers(build_stream_message(settings, repository), repository)


def build_stream_message(
    settings: AppSettings, repository: ConversationRepository
) -> StreamMessage:
    """Wire the graph, engine adapter, and use case from settings over a shared repository.

    The repository is injected (not built here) so the read-side conversations API and
    the write-side chat stream share one store — otherwise the sidebar sees an empty one.

    Example:
        use_case = build_stream_message(AppSettings(), InMemoryConversationRepository())
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
    return StreamMessage(
        repository, engine, DashboardViewBuilder(), get_logger("chat.stream_message")
    )


def _build_chat_model(settings: AppSettings, model_name: str) -> BaseChatModel:
    """Build a chat model from settings for the given model name."""
    return LiteLLMLanguageModel(
        model_name=model_name,
        temperature=settings.language_model_temperature,
        api_key=settings.openai_api_key,
        api_base=settings.openai_base_url,
    ).get_chat_model()
