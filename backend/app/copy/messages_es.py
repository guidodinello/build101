"""Fixed owner-facing text, from docs/product/conversation-design.md (copy deck).

The orchestrator writes what the Owner reads (ADR 0026): code emits an event
(`app/conversation/events.py`) and the model answers it with the conversation in view. So this
module holds only:

- fallbacks for when the LLM is unavailable: `REPLY_FAILED`, `STILL_WORKING`, `LOOKING_AT_PHOTOS`
  and the text of each event (`events.fallback`), sent only if that event's turn fails;
- text sent directly, outside the chat: `BRAND_GENERATING` (onboarding API, until T23);
- labels, not conversation: `carousel_slide`.
"""

STALE_BUTTON = "Ese botón ya no está activo 🙂"
UNSUPPORTED_MEDIA = (
    "Por ahora solo entiendo texto, audios, fotos y videos 🙏 ¿Me lo escribís o me mandás un audio?"
)
AUDIO_UNCLEAR = "No te llegué a entender el audio 🙈 ¿Me lo mandás de nuevo o me lo escribís?"
REPLY_FAILED = "Uy, se me trabó algo. ¿Me lo mandás de nuevo en un ratito?"
STILL_WORKING = "Un segundo, ya te respondo ⏳"
LOOKING_AT_PHOTOS = "Estoy mirando las fotos, ya te digo 👀"
JOB_FAILED = "Uy, se me trabó algo armando esto. ¿Lo intento de nuevo?"
# `photo_saved` without its buttons (T18) and without "la guardo para próximos posts": until
# T02 a photo is only kept for 30 minutes.
PHOTO_KEPT = "¡Buenísima! 📸 ¿Armo un post con esta foto?"
PHOTOS_KEPT = "¡Buenísimas! 📸 ¿Armo un post con estas fotos?"
PHOTO_UNREADABLE = "No pude abrir la foto 🙈 ¿Me la mandás de nuevo?"
PUBLISH_PENDING = "Instagram lo está procesando, en un ratito aparece en tu cuenta ⏳"
PUBLISH_FAILED = "Uy, Instagram no me dejó publicarlo 🙈 ¿Probamos armándolo de nuevo?"
BRAND_GENERATING = "¡Gracias! Estoy estudiando tu marca, en un minuto te cuento lo que entendí ⏳"


def photo_too_big(max_mb: int) -> str:
    return f"Esa foto es muy pesada 🙈 ¿Me mandás una más liviana? (hasta {max_mb} MB)"


def published(permalink: str) -> str:
    return f"¡Publicado! 🎉 {permalink}"


def carousel_slide(n: int, count: int) -> str:
    return f"{n}/{count}"
