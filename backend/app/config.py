from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["local", "prod"] = "local"
    # Set by Railway on deploys from GitHub (not on `railway up`); /ready reports it
    railway_git_commit_sha: str | None = None

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
    # AI-generated Reels (ADR 0033). Off by default: with VIDEO_GEN_ENABLED=false no video adapter
    # is built and nothing can call Veo. Its own key, never GEMINI_API_KEY.
    video_gen_enabled: bool = False
    video_gen: Literal["gemini", "mock"] = "mock"
    gemini_video_api_key: str | None = None
    gemini_video_model: str = "veo-3.1-lite-generate-preview"
    video_gen_max_concurrency: int = 1
    video_gen_timeout_s: int = 600
    # Designed slides are rendered by the frontend's Takumi route (ADR 0029); RENDERER_SECRET is
    # the frontend's RENDER_SECRET
    renderer: Literal["takumi", "mock"] = "mock"
    renderer_url: str | None = None
    renderer_secret: str | None = None

    # Replies to the Owner (ADR 0023). INBOUND_HANDLER = chat (Gemini) | echo (no LLM)
    inbound_handler: Literal["chat", "echo"] = "chat"
    gemini_chat_model: str = "gemini-3.8-flash"
    assistant_name: str = "Neitor"
    # Post images are served from here until Supabase Storage (T17); in local dev, the tunnel URL
    public_backend_url: str | None = None
    max_posts_per_day: int = 5
    # Videos are billed per second (ADR 0033), so they have their own cap, apart from designs
    max_videos_per_day: int = 2
    max_photo_mb: int = 10
    # A Niche Report saved by `python -m app.agents.niche_cli` (ADR 0025): its insights are the
    # trend notes of every sender, only when there is no database. With DATABASE_URL, the weekly
    # generate_niche_report job saves them in niche_reports, per niche, and this is ignored
    niche_report_path: Path | None = None

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

    # Reading the Owner's Instagram through our own Meta app (ADR 0028). INSTAGRAM = meta | mock
    instagram: Literal["meta", "mock"] = "mock"
    instagram_app_id: str | None = None
    instagram_app_secret: str | None = None
    instagram_graph_version: str = "v24.0"
    instagram_import_max_posts: int = 100
    instagram_import_max_images: int = 24

    @property
    def whatsapp_url(self) -> str:
        return f"https://wa.me/{self.whatsapp_bot_number or ''}"


# Kept working for the demo, never in front of a real Owner: the mock publisher answers that a
# Post is live when nothing reached Instagram
DEMO_FALLBACKS = frozenset({"mock", "echo", "simulator"})
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


def adapters_in_use(settings: Settings) -> dict[str, str]:
    """The adapter behind each port, by setting name: names only, never a key."""
    return {
        "IMAGE_GEN": settings.image_gen,
        "RENDERER": settings.renderer,
        "PUBLISHER": settings.publisher,
        "INSTAGRAM": settings.instagram,
        "VIDEO_GEN": settings.video_gen if settings.video_gen_enabled else "off",
        "INBOUND_HANDLER": settings.inbound_handler,
        "WHATSAPP_CHANNEL": settings.whatsapp_channel,
    }


def production_problems(settings: Settings) -> dict[str, str]:
    """Why each setting can't serve real Owners, by setting name; never its value."""
    problems = {
        name: "demo fallback"
        for name, adapter in adapters_in_use(settings).items()
        if adapter in DEMO_FALLBACKS
    }
    required = {
        "DATABASE_URL": settings.database_url,
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_SERVICE_ROLE_KEY": settings.supabase_service_role_key,
        "GEMINI_API_KEY": settings.gemini_api_key,
        "KAPSO_API_KEY": settings.kapso_api_key,
        "KAPSO_WEBHOOK_SECRET": settings.kapso_webhook_secret,
        "KAPSO_PHONE_NUMBER_ID": settings.kapso_phone_number_id,
        "RENDERER_SECRET": settings.renderer_secret,
        "ZERNIO_API_KEY": settings.zernio_api_key,
        # Every Post goes to the one demo account (ADR 0024)
        "ZERNIO_ACCOUNT_ID": settings.zernio_account_id,
        "INSTAGRAM_APP_ID": settings.instagram_app_id,
        "INSTAGRAM_APP_SECRET": settings.instagram_app_secret,
        "WHATSAPP_BOT_NUMBER": settings.whatsapp_bot_number,
    }
    if settings.video_gen_enabled:
        required["GEMINI_VIDEO_API_KEY"] = settings.gemini_video_api_key
    problems |= {name: "not set" for name, value in required.items() if not value}
    public_urls = {
        "PUBLIC_BACKEND_URL": [settings.public_backend_url or ""],
        "RENDERER_URL": [settings.renderer_url or ""],
        "FRONTEND_URL": [settings.frontend_url],
        "FRONTEND_ORIGINS": settings.frontend_origins.split(","),
    }
    for name, urls in public_urls.items():
        listed = [url.strip() for url in urls if url.strip()]
        if not listed:
            problems[name] = "not set"
        elif not all(_is_public(url) for url in listed):
            problems[name] = "not a public URL"
    return problems


def _is_public(url: str) -> bool:
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return False
    return host is not None and host not in LOCAL_HOSTS


def check_production(settings: Settings) -> None:
    """With ENV=prod, refuse to start on a demo fallback or a missing setting: Railway variables
    are typed by hand, and an unset or misspelled name falls back without a word."""
    if settings.env != "prod":
        return
    problems = production_problems(settings)
    if problems:
        listed = ", ".join(f"{name} ({problem})" for name, problem in problems.items())
        raise ValueError(f"ENV=prod refuses to start; fix these settings: {listed}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
