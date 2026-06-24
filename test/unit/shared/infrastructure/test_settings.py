import pytest

from shared.infrastructure.settings import AppSettings


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
