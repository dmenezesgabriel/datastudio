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
from shared.infrastructure.api.current_user import ResolveOwnerId
from shared.infrastructure.config.settings import AppSettings
from shared.infrastructure.sql_engine.duckdb.duckdb_sql_engine import DuckDbSqlEngine


def build_chat_routers(
    stream_message: StreamMessage,
    repository: ConversationRepository,
    resolve_current_user: ResolveOwnerId,
) -> list[APIRouter]:
    """Assemble chat's routers over a shared conversation store (abstractions injected).

    One store feeds both the write-side ``ChatRouter`` (via the use case) and the
    read-side ``ConversationsRouter`` — otherwise the sidebar sees an empty one.
    ``resolve_current_user`` is injected (not built here) so identity owns auth and
    chat stays ignorant of it.

    Example:
        routers = build_chat_routers(stream_message, repository, resolve_current_user)
        for router in routers:
            app.include_router(router)
    """
    return [
        ChatRouter(stream_message, resolve_current_user).router,
        ConversationsRouter(repository, resolve_current_user).router,
    ]


def build_chat_api(settings: AppSettings, resolve_current_user: ResolveOwnerId) -> list[APIRouter]:
    """Compose chat's HTTP surface from settings; self-contained for standalone deploy.

    ``resolve_current_user`` comes from the identity component (wired by the
    composition root) and scopes every conversation to its owning user.

    Example:
        for router in build_chat_api(AppSettings(), resolve_current_user):
            app.include_router(router)
    """
    repository = InMemoryConversationRepository()  # one shared store, by construction
    stream_message = build_stream_message(settings, repository)
    return build_chat_routers(stream_message, repository, resolve_current_user)


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
    return StreamMessage(repository, engine, DashboardViewBuilder())


def _build_chat_model(settings: AppSettings, model_name: str) -> BaseChatModel:
    """Build a chat model from settings for the given model name."""
    return LiteLLMLanguageModel(
        model_name=model_name,
        temperature=settings.language_model_temperature,
        api_key=settings.openai_api_key,
        api_base=settings.openai_base_url,
    ).get_chat_model()
