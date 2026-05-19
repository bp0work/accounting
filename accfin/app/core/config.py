from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="AI Finance Platform", alias="FINANCE_APP_NAME")
    app_env: str = Field(default="development", alias="FINANCE_APP_ENV")
    debug: bool = Field(default=False, alias="FINANCE_DEBUG")
    log_level: str = Field(default="INFO", alias="FINANCE_LOG_LEVEL")
    host: str = Field(default="0.0.0.0", alias="FINANCE_HOST")
    port: int = Field(default=8000, alias="FINANCE_PORT")

    database_url: str = Field(alias="FINANCE_DATABASE_URL")
    redis_host: str = Field(default="redis", alias="FINANCE_REDIS__HOST")
    redis_port: int = Field(default=6379, alias="FINANCE_REDIS__PORT")
    redis_db: int = Field(default=0, alias="FINANCE_REDIS__DB")
    redis_password: str = Field(alias="FINANCE_REDIS__PASSWORD")

    @property
    def version(self) -> str:
        return "0.1.0-phase1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
