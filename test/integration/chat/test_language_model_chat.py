import pytest
from langchain_core.messages import HumanMessage
from pytest_bdd import given, scenario, then, when

from chat.application.ports.response_content_extractor_port import ResponseContentExtractorPort
from chat.infrastructure.litellm_language_model import LiteLLMLanguageModel
from shared.infrastructure.settings import AppSettings


@pytest.mark.integration
@scenario("language_model_chat.feature", "Chat model returns a response to a simple prompt")
def test_chat_model_returns_response() -> None:
    pass


@given("a language model configured with OpenCode Go settings", target_fixture="chat_model")
def chat_model_fixture(app_settings: AppSettings):
    model = LiteLLMLanguageModel(
        model_name=app_settings.language_model_name,
        temperature=app_settings.language_model_temperature,
        api_key=app_settings.openai_api_key,
        api_base=app_settings.openai_base_url,
    )
    return model.get_chat_model()


@when('I send the prompt "Say hello in one word"', target_fixture="response")
def send_prompt(chat_model):
    return chat_model.invoke([HumanMessage(content="Say hello in one word")])


@then("I receive a non-empty text response")
def verify_response(response, content_extractor: ResponseContentExtractorPort) -> None:
    assert content_extractor.extract(response).strip()
