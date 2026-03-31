import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-5.2"
    database_url: str = "sqlite:///./life_system.db"
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
