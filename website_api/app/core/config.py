"""Settings — loaded once at startup from environment / .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "local"
    database_url: str = "sqlite:///./website.db"
    cors_origins: str = "https://www.agenticmarketintel.ai,https://agenticmarketintel.ai"


settings = Settings()
