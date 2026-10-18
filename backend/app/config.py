from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["local", "prod"] = "local"

    # ADR 0003. DATABASE_URL is Supabase's session pooler: postgresql+asyncpg://...
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None

    # The web wizard (T24): magic links point here, and the browser calls the API from these
    frontend_url: str = "http://localhost:3000"
    frontend_origins: str = "http://localhost:3000"
    whatsapp_bot_number: str | None = None  # for wa.me links, digits only

    enable_dev_endpoints: bool = False
    dev_token: str | None = None

    image_gen: Literal["gemini", "openai", "mock"] = "mock"
    gemini_api_key: str | None = None
    gemini_image_model: str = "gemini-nano-banana-2.1"
    gemini_thinking_level: Literal["minimal", "medium", "high"] = "medium"
    gemini_image_size: Literal["1K", "2K", "4K"] = "2K"
    image_gen_max_concurrency: int = 4

    # Replies to the Owner (ADR 0023). INBOUND_HANDLER = chat (Gemini) | echo (no LLM)
    inbound_handler: Literal["chat", "echo"] = "chat"
    gemini_chat_model: str = "gemini-3.8-flash"
    assistant_name: str = "Neitor"
    # Post images are served from here until Supabase Storage (T17); in local dev, the tunnel URL
    public_backend_url: str | None = None
    max_posts_per_day: int = 5
    max_photo_mb: int = 10

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

    @property
    def whatsapp_url(self) -> str:
        return f"https://wa.me/{self.whatsapp_bot_number or ''}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
