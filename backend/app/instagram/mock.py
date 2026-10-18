from datetime import UTC, datetime, timedelta
from io import BytesIO
from urllib.parse import urlencode

from PIL import Image

from .base import InstagramImage, InstagramMedia, InstagramProfile, InstagramToken

MOCK_CODE = "mock-code"
MOCK_USER_ID = "mock-ig-user"
MOCK_IMAGE_SIZE = (1080, 1350)
MOCK_POSTS = (
    ("Mesa de roble recién terminada para una familia de Pocitos 🌿 #muebles #roble", "sienna"),
    ("Así quedó el aparador restaurado. ¿Cuál es tu favorito? #restauracion", "olivedrab"),
    ("Taller abierto los sábados de 10 a 13. Escribinos por WhatsApp 🙌", "tan"),
)


class MockInstagram:
    """Offline InstagramPort: connects at once and imports three fake posts (local dev, demo)."""

    def authorize_url(self, redirect_uri: str, state: str) -> str:
        return f"{redirect_uri}?{urlencode({'code': MOCK_CODE, 'state': state})}"

    async def exchange_code(self, code: str, redirect_uri: str) -> InstagramToken:
        return InstagramToken(
            access_token=f"mock-token-{code}",
            user_id=MOCK_USER_ID,
            expires_at=datetime.now(UTC) + timedelta(days=60),
        )

    async def profile(self, access_token: str) -> InstagramProfile:
        return InstagramProfile(
            user_id=MOCK_USER_ID,
            username="tunegocio",
            name="Tu negocio",
            biography="Muebles de madera hechos a mano en Montevideo.",
            followers_count=1200,
            media_count=len(MOCK_POSTS),
        )

    async def recent_media(self, access_token: str, limit: int) -> list[InstagramMedia]:
        now = datetime.now(UTC)
        return [
            InstagramMedia(
                id=f"mock-media-{index}",
                media_type="IMAGE",
                caption=caption,
                permalink=f"https://instagram.com/p/MOCK-{index}",
                timestamp=now - timedelta(days=3 * index),
                like_count=40 - 10 * index,
                comments_count=5 - index,
                images=[InstagramImage(id=f"mock-media-{index}", url=f"mock://{color}")],
            )
            for index, (caption, color) in enumerate(MOCK_POSTS)
        ][:limit]

    async def download(self, url: str) -> tuple[bytes, str]:
        buffer = BytesIO()
        Image.new("RGB", MOCK_IMAGE_SIZE, url.removeprefix("mock://")).save(buffer, "JPEG")
        return buffer.getvalue(), "image/jpeg"
