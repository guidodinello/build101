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
    gemini_image_size: Literal["1K", "2K", "4K"] = "2K"
    image_gen_max_concurrency: int = 4

    whatsapp_channel: Literal["kapso", "simulator"] = "kapso"
    kapso_api_key: str | None = None
    kapso_webhook_secret: str | None = None
    kapso_phone_number_id: str | None = None
    kapso_base_url: str = "https://api.kapso.ai/meta/whatsapp/v24.0"

    # The MVP publishes to one demo Instagram account (ADR 0024); the ids replace
    # social_accounts until the database exists.
    publisher: Literal["zernio", "mock"] = "mock"
    zernio_api_key: str | None = None
    zernio_base_url: str = "https://zernio.com/api/v1"
    zernio_profile_id: str | None = None
    zernio_account_id: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
