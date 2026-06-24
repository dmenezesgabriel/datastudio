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


class TestAppSettingsLogLevel:
    def test_default_log_level_is_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Act
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

        # Assert
        assert settings.log_level == "INFO"

    def test_accepts_valid_log_level_debug(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        # Act
        settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

        # Assert
        assert settings.log_level == "DEBUG"

    def test_normalises_lowercase_to_uppercase(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
