from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings loaded from environment / .env file.

    Example:
        settings = AppSettings()
        print(settings.openai_api_key)
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str
    openai_base_url: str = "https://opencode.ai/zen/go/v1"
    language_model_name: str = "openai/glm-5"
    language_model_temperature: float = 0.0
    duckdb_path: str = "./dev_data/datastudio.duckdb"
