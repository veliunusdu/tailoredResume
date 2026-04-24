import sys

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # Adzuna API (Job Search)
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def check_api_keys(self) -> "Settings":
        """Warn if no LLM API keys are found."""
        keys = [self.anthropic_api_key, self.openai_api_key, self.gemini_api_key]
        if not any(k for k in keys if k and not k.startswith("your_")):
            # We don't exit to allow local Ollama fallback, but we warn loudly
            print(
                "WARNING: No valid LLM API keys (Anthropic, Gemini, OpenAI) found in .env. Falling back to Ollama/Mock.",
                file=sys.stderr,
            )
        return self


settings = Settings()
