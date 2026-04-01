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
    openai_model: str = "gpt-5.4"          # legacy fallback / planner default
    planner_model: str = "gpt-5.4"         # reasoning model — deep thinking
    executor_model: str = "gpt-5.3"        # execution model — fast, high quality

    # ── Model provider ────────────────────────────────────────────────────────
    model_provider: str = "openai"
    model_max_retries: int = 3
    model_timeout_s: int = 120
    model_repair_attempts: int = 1
    # Schema validation retry: how many additional attempts after a Pydantic failure
    schema_retry_attempts: int = 2

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./life_system.db"

    # ── Server ────────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    port: int = 8080

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


settings = Settings()
