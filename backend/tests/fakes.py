import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from app.agents.schemas import (
    Audience,
    BrandBrain,
    ContentPillar,
    PostingPrefs,
    VisualIdentity,
    Voice,
)
from app.channels.base import Button, ChannelError, ChannelPort
from app.conversation.events import Event
from app.imagegen.base import GeneratedImage
from app.llm.client import Content, FunctionCall, LLMError, Reply, Step, Tool
from app.publishing.base import PublishMedia, PublishResult
from app.storage import ObjectTooLarge, SignedUpload, StoredObject
from tests.conftest import make_image


def text_reply(text: str) -> Reply:
    steps = [
        {"type": "thought", "signature": "sig"},
        {"type": "model_output", "content": [{"type": "text", "text": text}]},
    ]
    return Reply(text=text, steps=steps)


def call_reply(name: str, call_id: str = "call_1", **arguments: Any) -> Reply:
    step = {"type": "function_call", "id": call_id, "name": name, "arguments": arguments}
    return Reply(text="", steps=[step], function_calls=[FunctionCall(call_id, name, arguments)])


@dataclass
class FakeChannel:
    sent: list[tuple[str, str]] = field(default_factory=list)
    images: list[tuple[str, str, str | None]] = field(default_factory=list)
    buttons: list[tuple[str, str, list[str]]] = field(default_factory=list)
    video_headers: list[str | None] = field(default_factory=list)
    read: list[tuple[str, bool]] = field(default_factory=list)
    downloads: list[str] = field(default_factory=list)
    media: bytes = field(default_factory=lambda: make_image((800, 1000)))
    fail_mark_read: bool = False

    async def send_text(self, to: str, text: str) -> str:
        self.sent.append((to, text))
        return "wamid.OUT"

    async def send_image(self, to: str, image_url: str, caption: str | None = None) -> str:
        self.images.append((to, image_url, caption))
        return "wamid.IMG"

    async def send_buttons(
        self,
        to: str,
        body: str,
        buttons: list[Button],
        header_image_url: str | None = None,
        header_video_url: str | None = None,
    ) -> str:
        # The body is a message the Owner reads, in order with the rest: `sent` keeps it too.
        self.sent.append((to, body))
        self.buttons.append((to, body, [button.id for button in buttons]))
        self.video_headers.append(header_video_url)
        return "wamid.BTN"

    async def mark_read(self, message_id: str, typing: bool = False) -> None:
        if self.fail_mark_read:
            raise ChannelError("boom")
        self.read.append((message_id, typing))

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        self.downloads.append(media_id)
        return self.media, "image/jpeg"


@dataclass
class EventLog:
    """A `Notify` that only records what code asked to tell the Owner."""

    events: list[tuple[str, Event]] = field(default_factory=list)

    async def __call__(self, sender: str, event: Event, channel: ChannelPort) -> None:
        self.events.append((sender, event))


@dataclass
class ScriptedModel:
    """Stands in for Gemini: replies in order (the last one repeats), drafts by schema."""

    replies: list[Reply] = field(default_factory=lambda: [text_reply("¡Hola! ¿Qué vendés?")])
    drafts: dict[type, BaseModel] = field(default_factory=dict)
    calls: list[list[Step]] = field(default_factory=list)
    systems: list[str] = field(default_factory=list)
    thinking: list[str] = field(default_factory=list)
    tools_seen: list[list[Tool] | None] = field(default_factory=list)
    structured_calls: list[list[Content]] = field(default_factory=list)
    structured_systems: list[str] = field(default_factory=list)
    fail: bool = False
    delay_s: float = 0.0

    async def reply(
        self,
        agent: str,
        system: str,
        history: list[Step],
        thinking_level: str,
        tools: list[Tool] | None = None,
    ) -> Reply:
        self.calls.append(history)
        self.systems.append(system)
        self.thinking.append(thinking_level)
        self.tools_seen.append(tools)
        await asyncio.sleep(self.delay_s)
        if self.fail:
            raise LLMError("boom")
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]

    async def structured[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: str,
    ) -> T:
        self.structured_calls.append(content)
        self.structured_systems.append(system)
        if schema not in self.drafts:
            raise LLMError(f"no {schema.__name__} draft scripted")
        return self.drafts[schema]  # type: ignore[return-value]


@dataclass
class CountingImageGen:
    calls: list[str] = field(default_factory=list)
    references: list[list[bytes]] = field(default_factory=list)
    gate: asyncio.Event | None = None  # when set, generations wait for it
    fail: bool = False

    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        style_image: bytes | None = None,
        *,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
    ) -> GeneratedImage:
        self.calls.append(prompt)
        self.references.append(reference_images)
        if self.gate is not None:
            await self.gate.wait()
        if self.fail:
            raise RuntimeError("image service down")
        return GeneratedImage(
            data=make_image((1080, 1350)), mime="image/jpeg", provider="fake", model=None, usage={}
        )


PERMALINK = "https://www.instagram.com/p/ABC123/"


@dataclass
class FakePublisher:
    """Stands in for Zernio: answers in order (the last repeats), raising the exceptions."""

    results: list[PublishResult | Exception] = field(
        default_factory=lambda: [
            PublishResult(status="published", external_post_id="ext-1", permalink=PERMALINK)
        ]
    )
    calls: list[dict[str, Any]] = field(default_factory=list)
    gate: asyncio.Event | None = None  # when set, publishing waits for it

    async def ensure_profile(self, name: str, external_id: str) -> str:
        return "profile"

    async def connect_url(self, profile_id: str, platform: str, redirect_url: str) -> str:
        return redirect_url

    async def publish(
        self,
        account_id: str,
        caption: str,
        media: PublishMedia,
        when: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> PublishResult:
        self.calls.append(
            {"account_id": account_id, "caption": caption, "media": media, "key": idempotency_key}
        )
        if self.gate is not None:
            await self.gate.wait()
        item = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(item, Exception):
            raise item
        return item


@dataclass
class FakeStorage:
    """Supabase Storage in memory. `put` is what the browser does with the signed upload URL."""

    objects: dict[str, bytes] = field(default_factory=dict)
    content_types: dict[str, str] = field(default_factory=dict)
    created_at: dict[str, datetime] = field(default_factory=dict)

    def put(self, bucket: str, path: str, data: bytes) -> None:
        self.objects[f"{bucket}/{path}"] = data
        self.created_at[f"{bucket}/{path}"] = datetime.now(UTC)

    def age(self, bucket: str, by: timedelta) -> None:
        """Make every object of the bucket `by` older (the sweep only takes the old ones)."""
        for key in self.created_at:
            if key.startswith(f"{bucket}/"):
                self.created_at[key] -= by

    async def create_signed_upload_url(self, bucket: str, path: str) -> SignedUpload:
        return SignedUpload(url=f"https://storage.test/upload/{bucket}/{path}?token=t", token="t")

    async def download(
        self, bucket: str, path: str, *, max_bytes: int | None = None
    ) -> bytes | None:
        data = self.objects.get(f"{bucket}/{path}")
        if data is not None and max_bytes is not None and len(data) > max_bytes:
            raise ObjectTooLarge(f"object is over {max_bytes} bytes")
        return data

    async def upload(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        self.put(bucket, path, data)
        self.content_types[f"{bucket}/{path}"] = content_type

    async def create_signed_urls(
        self, bucket: str, paths: list[str], expires_in_s: int
    ) -> dict[str, str]:
        return {
            path: f"https://storage.test/sign/{bucket}/{path}"
            for path in paths
            if f"{bucket}/{path}" in self.objects
        }

    async def remove(self, bucket: str, paths: list[str]) -> None:
        for path in paths:
            self.objects.pop(f"{bucket}/{path}", None)
            self.content_types.pop(f"{bucket}/{path}", None)
            self.created_at.pop(f"{bucket}/{path}", None)

    async def list_objects(self, bucket: str, prefix: str) -> list[StoredObject]:
        folder = f"{bucket}/{prefix}/"
        return [
            StoredObject(key.removeprefix(folder), created)
            for key, created in self.created_at.items()
            if key.startswith(folder) and "/" not in key.removeprefix(folder)
        ]


class CountingStorage(FakeStorage):
    """FakeStorage that counts the downloads asked of it."""

    downloads: int = 0

    async def download(
        self, bucket: str, path: str, *, max_bytes: int | None = None
    ) -> bytes | None:
        self.downloads += 1
        return await super().download(bucket, path, max_bytes=max_bytes)


def brand_brain(**changes: Any) -> BrandBrain:
    brain = BrandBrain(
        business_name="Katei",
        one_liner="Muebles restaurados",
        description="Restauramos muebles antiguos.",
        category="Muebles y deco",
        location="Montevideo",
        goal="sales",
        audiences=[Audience(name="Familias", description="", pains=[], motivations=[])],
        value_props=["Hecho a mano"],
        voice=Voice(
            descriptors=["cálido"],
            formality=2,
            humor=3,
            emoji_policy="few",
            do=[],
            dont=[],
            sample_phrases=[],
        ),
        pillars=[ContentPillar(id="taller", name="El taller", description="", example_ideas=[])],
        featured_products=[],
        ctas=["Escribinos"],
        hashtags=["#muebles"],
        posting=PostingPrefs(posts_per_week=2, preferred_days=["mon"], preferred_time="19:00"),
        constraints=[],
        visual_identity=VisualIdentity(
            primary_color="#111111",
            secondary_color="#222222",
            accent_color="#333333",
            background_color="#ffffff",
            text_color="#000000",
            logo_asset_id=None,
            photo_style="luz natural",
        ),
        whatsapp_summary="• *Cómo hablamos:* cálidos",
    )
    return brain.model_copy(update=changes)


@dataclass
class SequenceModel:
    """Structured answers in order, for agents that may call the model more than once."""

    answers: list[BaseModel]
    contents: list[list[Content]] = field(default_factory=list)
    gate: asyncio.Event | None = None  # when set, answers wait for it

    async def structured[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: str,
    ) -> T:
        self.contents.append(list(content))
        if self.gate is not None:
            await self.gate.wait()
        return self.answers.pop(0)  # type: ignore[return-value]
