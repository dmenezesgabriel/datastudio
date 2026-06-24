import pytest

from chat.application.ports.response_content_extractor_port import ResponseContentExtractorPort
from chat.infrastructure.response_content_extractor_factory import (
    create_response_content_extractor,
)
from shared.infrastructure.settings import AppSettings


@pytest.fixture(scope="session")
def app_settings() -> AppSettings:
    return AppSettings()


@pytest.fixture(scope="session")
def content_extractor(app_settings: AppSettings) -> ResponseContentExtractorPort:
    return create_response_content_extractor(api_base=app_settings.openai_base_url)
