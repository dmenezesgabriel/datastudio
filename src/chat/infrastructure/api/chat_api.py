"""HTTP assembly seam for the chat component.

Self-contained wiring for chat's FastAPI surface: ``build_chat_api`` composes the
object graph from settings, while ``build_chat_routers`` does the pure assembly
over injected collaborators. The composition root (``bootstrap.py``) mounts these
routers; keeping the seam here lets chat be deployed alone or alongside others.
"""

from fastapi import APIRouter
from langchain_core.language_models import BaseChatModel

from chat.application.ports.artifact_repository import ArtifactRepository
from chat.application.ports.conversation_repository import ConversationRepository
from chat.application.use_cases.delete_artifact import DeleteArtifact
from chat.application.use_cases.edit_artifact import EditArtifact
from chat.application.use_cases.list_dataset_tables import ListDatasetTables
from chat.application.use_cases.save_artifact import SaveArtifact
from chat.application.use_cases.set_artifact_version import SetArtifactVersion
from chat.application.use_cases.stream_message import StreamMessage
from chat.infrastructure.api.artifact_edit_router import ArtifactEditRouter
from chat.infrastructure.api.artifacts_router import ArtifactsRouter
from chat.infrastructure.api.chat_router import ChatRouter
from chat.infrastructure.api.conversations_router import ConversationsRouter
from chat.infrastructure.api.schema_router import SchemaRouter
from chat.infrastructure.graph.edit_dashboard_adapter import EditDashboardAdapter
from chat.infrastructure.graph.edit_graph import build_edit_graph
from chat.infrastructure.graph.litellm_language_model import LiteLLMLanguageModel
from chat.infrastructure.graph.text2sql_engine_adapter import Text2SqlEngineAdapter
from chat.infrastructure.graph.text2sql_graph import build_text2sql_graph
from chat.infrastructure.persistence.in_memory_artifact_repository import (
    InMemoryArtifactRepository,
)
from chat.infrastructure.persistence.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from chat.infrastructure.view.dashboard_view_builder import SpecStreamDashboardViewBuilder
from shared.application.ports.sql_engine_port import SqlEnginePort
from shared.infrastructure.api.current_user import ResolveOwnerId
from shared.infrastructure.config.settings import AppSettings
from shared.infrastructure.sql_engine.duckdb.duckdb_sql_engine import DuckDbSqlEngine


def build_chat_routers(
    stream_message: StreamMessage,
    conversation_repository: ConversationRepository,
    edit_artifact: EditArtifact,
    artifact_repository: ArtifactRepository,
    sql_engine: SqlEnginePort,
    resolve_current_user: ResolveOwnerId,
) -> list[APIRouter]:
    """Assemble chat's routers over its shared conversation and artifact stores.

    Each store feeds both its write and read routers (the conversation store feeds the
    chat stream + sidebar; the artifact store feeds the edit stream + gallery/CRUD) —
    otherwise a reader sees an empty one. ``sql_engine`` is injected for the same reason:
    the schema the composer offers as mentions must come from the engine that answers the
    questions. ``resolve_current_user`` is injected (not built here) so identity owns auth
    and chat stays ignorant of it.

    Example:
        routers = build_chat_routers(stream, conv_repo, edit, art_repo, engine, resolve)
        for router in routers:
            app.include_router(router)
    """
    save_artifact = SaveArtifact(artifact_repository)
    set_artifact_version = SetArtifactVersion(artifact_repository)
    delete_artifact = DeleteArtifact(artifact_repository)
    return [
        ChatRouter(stream_message, resolve_current_user).router,
        ConversationsRouter(conversation_repository, resolve_current_user).router,
        ArtifactsRouter(
            artifact_repository,
            save_artifact,
            set_artifact_version,
            delete_artifact,
            resolve_current_user,
        ).router,
        ArtifactEditRouter(edit_artifact, artifact_repository, resolve_current_user).router,
        SchemaRouter(ListDatasetTables(sql_engine), resolve_current_user).router,
    ]


def build_chat_api(settings: AppSettings, resolve_current_user: ResolveOwnerId) -> list[APIRouter]:
    """Compose chat's HTTP surface from settings; self-contained for standalone deploy.

    ``resolve_current_user`` comes from the identity component (wired by the
    composition root) and scopes every conversation and artifact to its owning user.

    Example:
        for router in build_chat_api(AppSettings(), resolve_current_user):
            app.include_router(router)
    """
    conversation_repository = InMemoryConversationRepository()  # one shared store, by construction
    artifact_repository = InMemoryArtifactRepository()  # shared by the CRUD API and the edit stream
    stream_message = build_stream_message(settings, conversation_repository, artifact_repository)
    edit_artifact = build_edit_artifact(settings, artifact_repository)
    return build_chat_routers(
        stream_message,
        conversation_repository,
        edit_artifact,
        artifact_repository,
        DuckDbSqlEngine(settings.duckdb_path),
        resolve_current_user,
    )


def build_stream_message(
    settings: AppSettings,
    repository: ConversationRepository,
    artifact_repository: ArtifactRepository,
) -> StreamMessage:
    """Wire the graph, engine adapter, and use case from settings over shared repositories.

    Both stores are injected (not built here): the conversation store so the sidebar and
    chat stream share one, and the artifact store so every dashboard/widget the turn
    auto-saves lands in the same gallery the CRUD API serves.

    Example:
        use_case = build_stream_message(AppSettings(), conv_repo, InMemoryArtifactRepository())
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
    return StreamMessage(repository, engine, SpecStreamDashboardViewBuilder(), artifact_repository)


def build_edit_artifact(settings: AppSettings, repository: ArtifactRepository) -> EditArtifact:
    """Wire the edit graph, edit engine, and use case from settings over a shared repository.

    The repository is injected (not built here) so the CRUD artifacts API and the write-side
    edit stream share one store — otherwise the gallery never sees an edit's new version.

    Example:
        use_case = build_edit_artifact(AppSettings(), InMemoryArtifactRepository())
    """
    chat_model = _build_chat_model(settings, settings.language_model_name)
    format_chat_model = _build_chat_model(settings, settings.format_model_name)
    graph = build_edit_graph(
        chat_model,
        DuckDbSqlEngine(settings.duckdb_path),
        format_chat_model=format_chat_model,
        api_base=settings.openai_base_url,
    )
    engine = EditDashboardAdapter(graph, timeout_s=settings.query_timeout_s)
    return EditArtifact(repository, engine, SpecStreamDashboardViewBuilder())


def _build_chat_model(settings: AppSettings, model_name: str) -> BaseChatModel:
    """Build a chat model from settings for the given model name."""
    return LiteLLMLanguageModel(
        model_name=model_name,
        temperature=settings.language_model_temperature,
        api_key=settings.openai_api_key,
        api_base=settings.openai_base_url,
    ).get_chat_model()
