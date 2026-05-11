"""Application settings loaded from environment variables and .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration consumed by the application at startup.

    Values are read from a ``.env`` file at the project root.
    Set ``USE_MOCK_CLAUDE=true`` to skip real API calls during development.
    """

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_api_url: str = "https://api.anthropic.com/v1/messages"
    use_mock_claude: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
