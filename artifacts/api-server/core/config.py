import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_base_url: str = ""

    # Two-tier model architecture:
    #   planner_model  — reasoning model for high-level planning stages (system_architecture)
    #   executor_model — fast model for all content-generation stages (worksheets, layout, etc.)
    # The contract's model_role field ("planner" | "executor") selects which model to use.
    openai_model: str = "gpt-5.4"          # legacy fallback
    planner_model: str = "gpt-5.4"         # reasoning model — complex planning stages
    executor_model: str = "gpt-5.4"        # execution model — chapter content, appendix, etc.

    # ── Model provider ────────────────────────────────────────────────────────
    model_provider: str = "openai"
    model_max_retries: int = 3
    model_timeout_s: int = 300
    model_repair_attempts: int = 1
    # Schema validation retry: how many additional attempts after a Pydantic failure
    schema_retry_attempts: int = 2

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./life_system.db"

    # ── Chapter expansion concurrency ─────────────────────────────────────────
    # Number of parallel workers for the chapter_expansion stage.
    # Reduce if hitting rate limits; increase on high-concurrency OpenAI tiers.
    chapter_expansion_workers: int = 4

    # ── Server / CORS ─────────────────────────────────────────────────────────
    log_level: str = "INFO"
    port: int = 8080

    # Comma-separated allowed frontend origins, e.g.:
    #   ALLOWED_ORIGINS=https://myapp.replit.app,https://myapp.com
    # Leave empty in development to allow all origins (credentials disabled).
    allowed_origins: str = ""

    # ── Auth ──────────────────────────────────────────────────────────────────
    # Set API_KEY to enable simple API-key auth on all mutation endpoints.
    # If unset the server runs in open (development) mode.
    api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

    def get_openai_api_key(self) -> str:
        return (
            os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or self.openai_api_key
        )

    def get_openai_base_url(self) -> str | None:
        return (
            os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
            or (self.openai_base_url if self.openai_base_url else None)
        )

    def get_allowed_origins(self) -> list[str]:
        raw = os.environ.get("ALLOWED_ORIGINS", self.allowed_origins).strip()
        if not raw:
            return []
        return [o.strip() for o in raw.split(",") if o.strip()]

    def get_api_key(self) -> str:
        return os.environ.get("API_KEY", self.api_key).strip()


settings = Settings()
