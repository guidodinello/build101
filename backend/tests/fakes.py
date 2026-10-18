import asyncio
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from app.channels.base import ChannelError
from app.imagegen.base import GeneratedImage
from app.llm.client import Content, FunctionCall, LLMError, Reply, Step, Tool
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

    async def mark_read(self, message_id: str, typing: bool = False) -> None:
        if self.fail_mark_read:
            raise ChannelError("boom")
        self.read.append((message_id, typing))

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        self.downloads.append(media_id)
        return self.media, "image/jpeg"


@dataclass
class ScriptedModel:
    """Stands in for Gemini: replies in order (the last one repeats), drafts by schema."""

    replies: list[Reply] = field(default_factory=lambda: [text_reply("¡Hola! ¿Qué vendés?")])
    drafts: dict[type, BaseModel] = field(default_factory=dict)
    calls: list[list[Step]] = field(default_factory=list)
    tools_seen: list[list[Tool] | None] = field(default_factory=list)
    structured_calls: list[list[Content]] = field(default_factory=list)
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
        return self.drafts[schema]  # type: ignore[return-value]


@dataclass
class CountingImageGen:
    calls: list[str] = field(default_factory=list)
    references: list[list[bytes]] = field(default_factory=list)
    gate: asyncio.Event | None = None  # when set, generations wait for it
    fail: bool = False

    async def generate(
        self, prompt: str, reference_images: list[bytes], style_image: bytes | None = None
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
