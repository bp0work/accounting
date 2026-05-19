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

    jwt_secret: str = Field(alias="FINANCE_JWT__SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="FINANCE_JWT__ALGORITHM")
    jwt_access_expire_minutes: int = Field(default=15, alias="FINANCE_JWT__ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_expire_days: int = Field(default=7, alias="FINANCE_JWT__REFRESH_TOKEN_EXPIRE_DAYS")
    jwt_issuer: str = Field(default="finance-platform", alias="FINANCE_JWT__ISSUER")
    jwt_audience: str = Field(default="finance-api", alias="FINANCE_JWT__AUDIENCE")

    privacy_encryption_key: str = Field(alias="FINANCE_PRIVACY_ENCRYPTION_KEY")
    totp_issuer: str = Field(default="mmlogistix-finance", alias="FINANCE_TOTP__ISSUER")

    max_failed_login_attempts: int = Field(default=5)
    lockout_minutes: int = Field(default=30)
    # Sixth failed attempt returns 429 (counter reaches 5 before the 6th call).
    login_rate_limit_attempts: int = Field(default=5)

    @property
    def version(self) -> str:
        return "0.2.0-phase2"


@lru_cache
def get_settings() -> Settings:
    return Settings()
