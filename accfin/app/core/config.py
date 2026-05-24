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

    intake_queue_name: str = Field(default="intake_queue", alias="FINANCE_MAIL__INTAKE_QUEUE")
    accounts_queue_name: str = Field(default="accounts_queue", alias="FINANCE_ORCHESTRATOR__ACCOUNTS_QUEUE")
    dead_letter_queue_name: str = Field(
        default="dead_letter_queue", alias="FINANCE_ORCHESTRATOR__DEAD_LETTER_QUEUE"
    )
    retry_queue_name: str = Field(default="retry_queue", alias="FINANCE_ORCHESTRATOR__RETRY_QUEUE")
    orchestrator_enabled: bool = Field(default=True, alias="FINANCE_ORCHESTRATOR__ENABLED")
    orchestrator_port: int = Field(default=8003, alias="FINANCE_ORCHESTRATOR_PORT")
    accounts_worker_enabled: bool = Field(default=True, alias="FINANCE_ACCOUNTS_WORKER__ENABLED")
    accounts_worker_port: int = Field(default=8010, alias="FINANCE_ACCOUNTS_WORKER_PORT")
    ar_worker_enabled: bool = Field(default=True, alias="FINANCE_AR_WORKER__ENABLED")
    ar_worker_port: int = Field(default=8011, alias="FINANCE_AR_WORKER_PORT")
    ap_worker_enabled: bool = Field(default=True, alias="FINANCE_AP_WORKER__ENABLED")
    ap_worker_port: int = Field(default=8012, alias="FINANCE_AP_WORKER_PORT")
    treasury_worker_enabled: bool = Field(default=True, alias="FINANCE_TREASURY_WORKER__ENABLED")
    treasury_worker_port: int = Field(default=8013, alias="FINANCE_TREASURY_WORKER_PORT")
    expense_worker_enabled: bool = Field(default=True, alias="FINANCE_EXPENSE_WORKER__ENABLED")
    expense_worker_port: int = Field(default=8014, alias="FINANCE_EXPENSE_WORKER_PORT")
    reconciliation_amount_tolerance_pct: float = Field(
        default=0.01, alias="FINANCE_RECONCILIATION_AMOUNT_TOLERANCE_PCT"
    )
    hermes_base_url: str = Field(default="http://hermes:8001", alias="FINANCE_HERMES__BASE_URL")
    attachment_storage_path: str = Field(
        default="/data/attachments", alias="FINANCE_MAIL__ATTACHMENT_STORAGE_PATH"
    )
    mail_poll_enabled: bool = Field(default=True, alias="FINANCE_MAIL__POLL_ENABLED")
    mail_poll_interval_seconds: int = Field(
        default=60, alias="FINANCE_MAIL__POLL_INTERVAL_SECONDS"
    )

    max_failed_login_attempts: int = Field(default=5)
    lockout_minutes: int = Field(default=30)
    # Sixth failed attempt returns 429 (counter reaches 5 before the 6th call).
    login_rate_limit_attempts: int = Field(default=5)

    prometheus_enabled: bool = Field(default=True, alias="FINANCE_PROMETHEUS__ENABLED")
    prometheus_path: str = Field(default="/metrics", alias="FINANCE_PROMETHEUS__PATH")

    internal_cron_token: str = Field(default="", alias="FINANCE_INTERNAL_CRON__TOKEN")
    mail_action_secret: str = Field(default="", alias="FINANCE_MAIL_ACTION__SECRET")
    hash_secret: str = Field(default="", alias="FINANCE_HASH_SECRET")
    daily_log_recipient: str = Field(
        default="cfo.mmlogistix@bp0.work", alias="FINANCE_DAILY_LOG_RECIPIENT"
    )
    daily_log_timezone: str = Field(default="Asia/Singapore", alias="FINANCE_DAILY_LOG_TIMEZONE")
    daily_log_csv_utf8_bom: bool = Field(default=True, alias="FINANCE_DAILY_LOG__CSV_UTF8_BOM")
    wasabi_prefix_logs: str = Field(default="logs/", alias="FINANCE_WASABI__PREFIX_LOGS")
    smtp_enabled: bool = Field(default=False, alias="FINANCE_SMTP__ENABLED")

    internal_api_base_url: str = Field(
        default="http://fastapi:8000", alias="FINANCE_INTERNAL__API_BASE_URL"
    )
    public_app_host: str = Field(
        default="finance.mmlogistix.bp0.work", alias="FINANCE_PUBLIC__APP_HOST"
    )
    public_platform_admin_host: str = Field(
        default="admin.bp0.work", alias="FINANCE_PUBLIC__PLATFORM_ADMIN_HOST"
    )
    public_client_admin_host: str = Field(
        default="admin.mmlogistix.bp0.work", alias="FINANCE_PUBLIC__CLIENT_ADMIN_HOST"
    )

    @property
    def version(self) -> str:
        return "0.13.6-finance-security-2fa"

    @property
    def edge_public_base_url(self) -> str:
        """HTTPS origin for browser and signed email links (API paths on same host)."""
        return f"https://{self.public_app_host}"

    @property
    def cors_origins(self) -> list[str]:
        origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            self.edge_public_base_url,
            f"https://{self.public_platform_admin_host}",
            f"https://{self.public_client_admin_host}",
        ]
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
