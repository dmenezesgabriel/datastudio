import pytest
from pydantic import ValidationError

from shared.infrastructure.config.settings import AppSettings


class TestAppSettings:
    def test_loads_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")

        # Act
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

        # Assert
        assert settings.openai_api_key == "test-key-123"

    def test_default_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Act
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

        # Assert
        assert settings.openai_base_url == "https://opencode.ai/zen/go/v1"

    def test_default_model_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Act
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

        # Assert
        assert settings.language_model_name == "openai/glm-5"

    def test_custom_model_name_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("LANGUAGE_MODEL_NAME", "openai/glm-5")

        # Act
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

        # Assert
        assert settings.language_model_name == "openai/glm-5"

    def test_ignores_unknown_keys_in_env_file(
        self, tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — env file contains fields unknown to AppSettings. Clear the
        # process env first: importing litellm elsewhere runs load_dotenv(),
        # which would otherwise shadow _env_file (os.environ outranks it).
        for key in ("OPENAI_API_KEY", "KAGGLE_USERNAME", "KAGGLE_KEY"):
            monkeypatch.delenv(key, raising=False)
        env_file = tmp_path / ".env"  # type: ignore[operator]
        env_file.write_text("OPENAI_API_KEY=test-key\nKAGGLE_USERNAME=someone\nKAGGLE_KEY=secret\n")

        # Act / Assert — must not raise
        settings = AppSettings(_env_file=str(env_file))  # type: ignore[call-arg]
        assert settings.openai_api_key == "test-key"

    def test_query_timeout_defaults_to_120(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        # Act
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
        # Assert
        assert settings.query_timeout_s == 120.0


class TestAppSettingsLogLevel:
    def test_default_log_level_is_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Act
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

        # Assert
        assert settings.log_level == "INFO"

    def test_accepts_valid_log_level_debug(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        # Act
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

        # Assert
        assert settings.log_level == "DEBUG"

    def test_normalises_lowercase_to_uppercase(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("LOG_LEVEL", "debug")

        # Act
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

        # Assert
        assert settings.log_level == "DEBUG"

    def test_rejects_invalid_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("LOG_LEVEL", "VERBOSE")

        # Act / Assert
        with pytest.raises(ValidationError, match="log_level"):
            AppSettings(_env_file=None)  # type: ignore[call-arg]
