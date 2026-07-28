from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://grid:grid@localhost:5432/grid_copilot"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
