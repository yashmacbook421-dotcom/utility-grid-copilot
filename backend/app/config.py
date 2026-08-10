from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://grid:grid@localhost:5432/grid_copilot"
    anthropic_api_key: str = ""
    eia_api_key: str = ""
    claude_model: str = "claude-sonnet-5"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    cors_origins: str = "http://localhost:3000"
    surge_check_interval_seconds: int = 60
    slack_webhook_url: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_to_number: str = ""
    # Keep authentication off for the self-contained local demo.  Any
    # internet-reachable deployment must set AUTH_REQUIRED=true and provide
    # both keys through its secret manager.
    auth_required: bool = False
    operator_api_key: str = ""
    admin_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
