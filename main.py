from chat.infrastructure.litellm_language_model import LiteLLMLanguageModel
from shared.infrastructure.settings import AppSettings


def main() -> None:
    settings = AppSettings()
    language_model = LiteLLMLanguageModel(
        model_name=settings.language_model_name,
        temperature=settings.language_model_temperature,
        api_key=settings.openai_api_key,
        api_base=settings.openai_base_url,
    )
    chat_model = language_model.get_chat_model()
    print(f"Model ready: {chat_model.model}")


if __name__ == "__main__":
    main()
