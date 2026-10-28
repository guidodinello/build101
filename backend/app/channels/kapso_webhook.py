import hashlib
import hmac
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, ValidationError

from .base import Button, ChannelError, InboundAudio, InboundMedia, InboundMessage

# Kapso webhook v2 (confirmed 2026-10-17): top level `message`, `conversation`,
# `phone_number_id`. `message` has Meta-style fields plus a `kapso` block.
MESSAGE_RECEIVED_EVENT = "whatsapp.message.received"
# A message we sent that WhatsApp could not deliver, e.g. 131047 outside the 24 h window (#204).
MESSAGE_FAILED_EVENT = "whatsapp.message.failed"
# How deep `failure_codes` looks for Meta's `errors` arrays in a failed-message event.
MAX_ERROR_DEPTH = 6

# The HMAC covers the body only, so a captured body stays valid forever; one older than this is
# acknowledged and dropped (#105). Kapso delivers within seconds and retries about twice.
REPLAY_WINDOW_S = 3600


# Models for the parts of the webhook we read; unknown fields are ignored. Only what a message
# kind needs is strict (`from`, the ids, the text body, the button, the audio mime type), and a
# kind's block is validated only for that kind. Everything else degrades to absent, as it always
# has: null, a wrong type or a non-object block.
def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_none(value: object) -> int | None:
    if not isinstance(value, str | int | float):
        return None
    try:
        return int(value)
    except (ValueError, OverflowError):
        return None


def _object_or_none(value: object) -> object:
    return value if isinstance(value, dict) else None


type _Optional[M: BaseModel] = Annotated[M | None, BeforeValidator(_object_or_none)]
type _Block = Annotated[dict[str, Any] | None, BeforeValidator(_object_or_none)]
type _OptStr = Annotated[str | None, BeforeValidator(_str_or_none)]


class _TextBody(BaseModel):
    body: str


class _ButtonReply(BaseModel):
    id: str
    title: str


class _Image(BaseModel):
    id: str
    caption: _OptStr = None
    mime_type: _OptStr = None


class _Audio(BaseModel):
    id: str
    mime_type: str


class _Unsupported(BaseModel):
    type: object = None


class _MediaData(BaseModel):
    byte_size: Annotated[int | None, BeforeValidator(_int_or_none)] = None


class _MessageTypeData(BaseModel):
    caption: _OptStr = None


class _Transcript(BaseModel):
    text: _OptStr = None


class _Kapso(BaseModel):
    media_url: _OptStr = None
    media_data: _Optional[_MediaData] = None
    message_type_data: _Optional[_MessageTypeData] = None
    transcript: _Optional[_Transcript] = None


class _Message(BaseModel):
    id: _OptStr = None
    sender: str = Field(validation_alias="from")
    type: object = None
    timestamp: Annotated[int | None, BeforeValidator(_int_or_none)] = None
    text: _Block = None
    interactive: _Block = None
    image: _Block = None
    audio: _Block = None
    unsupported: _Optional[_Unsupported] = None
    kapso: _Optional[_Kapso] = None


class _Webhook(BaseModel):
    message: _Message
    phone_number_id: str


def verify_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """X-Webhook-Signature is the hex HMAC-SHA256 of the raw body with the webhook secret."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def is_stale(message: InboundMessage, now: float) -> bool:
    """Older than the replay window. No timestamp counts as fresh: dedupe still applies."""
    return message.timestamp is not None and message.timestamp < now - REPLAY_WINDOW_S


def parse_message(payload: dict[str, Any], fallback_id: str | None = None) -> InboundMessage:
    """Map a `whatsapp.message.received` payload; ChannelError when it lacks what its kind needs."""
    try:
        return _to_inbound(_Webhook.model_validate(payload), payload, fallback_id)
    except ValidationError as exc:
        raise ChannelError(f"unusable kapso webhook payload: {exc.error_count()} errors") from exc


def _to_inbound(webhook: _Webhook, raw: dict[str, Any], fallback_id: str | None) -> InboundMessage:
    message = webhook.message
    kapso = message.kapso or _Kapso()
    message_id = message.id or fallback_id
    if not message_id:
        raise ChannelError("kapso webhook message has no id")
    common: dict[str, Any] = {
        "message_id": message_id,
        "sender": message.sender,
        "phone_number_id": webhook.phone_number_id,
        "timestamp": message.timestamp,
        "raw": raw,
    }
    match message.type:
        case "text":
            text = _TextBody.model_validate(_required(message.text, "text"))
            return InboundMessage(kind="text", text=text.body, **common)
        case "interactive" if "button_reply" in (message.interactive or {}):
            reply = _ButtonReply.model_validate((message.interactive or {})["button_reply"])
            button = Button(id=reply.id, title=reply.title)
            return InboundMessage(kind="button", button=button, **common)
        case "image":
            image = _Image.model_validate(_required(message.image, "image"))
            caption = image.caption or (kapso.message_type_data or _MessageTypeData()).caption
            return InboundMessage(
                kind="image",
                text=caption,
                media=_media(image.mime_type, kapso, image.id),
                **common,
            )
        case "audio":
            audio = _Audio.model_validate(_required(message.audio, "audio"))
            transcript = ((kapso.transcript or _Transcript()).text or "").strip()
            return InboundMessage(
                kind="audio",
                audio=InboundAudio(
                    media_id=audio.id,
                    mime_type=audio.mime_type,
                    byte_size=(kapso.media_data or _MediaData()).byte_size,
                    provider_transcript=transcript or None,
                ),
                media=_media(audio.mime_type, kapso, audio.id),
                **common,
            )
        # WhatsApp announces an album with this message, then sends each photo on its own.
        case "unsupported" if message.unsupported and message.unsupported.type == "album":
            return InboundMessage(kind="album", **common)
        case _:
            return InboundMessage(kind="other", **common)


def _required[T](block: T | None, kind: str) -> T:
    if block is None:
        raise ChannelError(f"kapso {kind} message has no {kind} block")
    return block


def _media(mime_type: str | None, kapso: _Kapso, media_id: str) -> InboundMedia:
    return InboundMedia(
        media_id=media_id,
        url=kapso.media_url,
        mime_type=mime_type,
        byte_size=(kapso.media_data or _MediaData()).byte_size,
    )


def failed_message_id(payload: object) -> str | None:
    """The `wamid` of the message a failed-message event is about."""
    message = payload.get("message") if isinstance(payload, dict) else None
    return _str_or_none(message.get("id")) if isinstance(message, dict) else None


def failure_codes(payload: object, depth: int = 0) -> list[str]:
    """Every WhatsApp error code in a failed-message event, in order.

    Kapso's v2 event keeps Meta's message fields plus its own `kapso` block; where it puts Meta's
    `errors` array (`[{"code": 131047, "title": ...}]`) is not confirmed, so any `errors` array is
    read, at any depth up to `MAX_ERROR_DEPTH`.
    """
    if depth > MAX_ERROR_DEPTH:
        return []
    codes: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "errors" and isinstance(value, list):
                codes += [
                    str(error["code"])
                    for error in value
                    if isinstance(error, dict) and isinstance(error.get("code"), int | str)
                ]
            else:
                codes += failure_codes(value, depth + 1)
    elif isinstance(payload, list):
        for item in payload:
            codes += failure_codes(item, depth + 1)
    return codes
