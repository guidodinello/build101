import hashlib
import hmac
from typing import Any

from .base import Button, InboundAudio, InboundMedia, InboundMessage

# Kapso webhook v2 (confirmed 2026-10-17): top level `message`, `conversation`,
# `phone_number_id`. `message` has Meta-style fields plus a `kapso` block.
MESSAGE_RECEIVED_EVENT = "whatsapp.message.received"


def verify_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """X-Webhook-Signature is the hex HMAC-SHA256 of the raw body with the webhook secret."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_message(payload: dict[str, Any], fallback_id: str | None = None) -> InboundMessage:
    message = payload["message"]
    kapso = message.get("kapso") or {}
    message_id = message.get("id") or fallback_id
    if not message_id:
        raise KeyError("id")
    common: dict[str, Any] = {
        "message_id": message_id,
        "sender": message["from"],
        "phone_number_id": payload["phone_number_id"],
        "timestamp": _int_or_none(message.get("timestamp")),
        "raw": payload,
    }
    match message.get("type"):
        case "text":
            return InboundMessage(kind="text", text=message["text"]["body"], **common)
        case "interactive" if "button_reply" in (message.get("interactive") or {}):
            reply = message["interactive"]["button_reply"]
            button = Button(id=reply["id"], title=reply["title"])
            return InboundMessage(kind="button", button=button, **common)
        case "image":
            image = message["image"]
            caption = image.get("caption") or (kapso.get("message_type_data") or {}).get("caption")
            return InboundMessage(
                kind="image", text=caption, media=_media(image, kapso, image["id"]), **common
            )
        case "audio":
            audio = message["audio"]
            transcript = ((kapso.get("transcript") or {}).get("text") or "").strip()
            return InboundMessage(
                kind="audio",
                audio=InboundAudio(
                    media_id=audio["id"],
                    mime_type=audio["mime_type"],
                    byte_size=(kapso.get("media_data") or {}).get("byte_size"),
                    provider_transcript=transcript or None,
                ),
                media=_media(audio, kapso, audio["id"]),
                **common,
            )
        # WhatsApp announces an album with this message, then sends each photo on its own.
        case "unsupported" if (message.get("unsupported") or {}).get("type") == "album":
            return InboundMessage(kind="album", **common)
        case _:
            return InboundMessage(kind="other", **common)


def _media(content: dict[str, Any], kapso: dict[str, Any], media_id: str) -> InboundMedia:
    media_data = kapso.get("media_data") or {}
    return InboundMedia(
        media_id=media_id,
        url=kapso.get("media_url"),
        mime_type=content.get("mime_type"),
        byte_size=media_data.get("byte_size"),
    )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
