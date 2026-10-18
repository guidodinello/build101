"""Fixed owner-facing messages, from docs/product/conversation-design.md (copy deck)."""

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


def photo_too_big(max_mb: int) -> str:
    return f"Esa foto es muy pesada 🙈 ¿Me mandás una más liviana? (hasta {max_mb} MB)"


def carousel_slide(n: int, count: int) -> str:
    return f"{n}/{count}"
