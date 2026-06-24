import pytest

from chat.infrastructure.graph.response_content_extractor import (
    ResponseContentExtractor,
)
from chat.infrastructure.graph.response_content_extractor_factory import (
    create_response_content_extractor,
)
from shared.infrastructure.config.settings import AppSettings


@pytest.fixture(scope="session")
def app_settings() -> AppSettings:
    return AppSettings()


@pytest.fixture(scope="session")
def content_extractor(app_settings: AppSettings) -> ResponseContentExtractor:
    return create_response_content_extractor(api_base=app_settings.openai_base_url)
