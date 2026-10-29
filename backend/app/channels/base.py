from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class Button(BaseModel):
    id: str = Field(max_length=256)
    title: str = Field(max_length=20)


@runtime_checkable
class ChannelPort(Protocol):
    async def send_text(self, to: str, text: str) -> str: ...

    async def send_image(self, to: str, image_url: str, caption: str | None = None) -> str: ...

    async def send_buttons(
        self,
        to: str,
        body: str,
        buttons: list[Button],
        header_image_url: str | None = None,
        header_video_url: str | None = None,
    ) -> str: ...

    async def mark_read(self, message_id: str, typing: bool = False) -> None: ...

    async def download_media(self, media_id: str) -> tuple[bytes, str]: ...


class InboundMedia(BaseModel):
    media_id: str
    url: str | None = None
    mime_type: str | None = None
    byte_size: int | None = None


class InboundAudio(BaseModel):
    media_id: str
    mime_type: str
    byte_size: int | None = None
    # Kapso's transcript or, when it sent none, the fallback transcriber's (ADR 0021)
    transcript: str | None = None
    # Over MAX_AUDIO_MB with no transcript of Kapso's: never sent to the transcriber
    too_long: bool = False


class InboundMessage(BaseModel):
    kind: Literal["text", "button", "image", "audio", "album", "other"]
    message_id: str
    sender: str
    phone_number_id: str
    timestamp: int | None = None
    text: str | None = None  # the body, or the caption of an image
    button: Button | None = None
    media: InboundMedia | None = None
    audio: InboundAudio | None = None
    raw: dict[str, Any] = Field(repr=False)


class ChannelError(Exception):
    pass
