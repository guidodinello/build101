from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["local", "prod"] = "local"

    image_gen: Literal["gemini", "openai", "mock"] = "mock"
    gemini_api_key: str | None = None
    gemini_image_model: str = "gemini-nano-banana-2.1"
    gemini_thinking_level: Literal["minimal", "medium", "high"] = "medium"
    image_gen_max_concurrency: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
