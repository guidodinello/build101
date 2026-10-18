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
PUBLISH_PENDING = "Instagram lo está procesando, en un ratito aparece en tu cuenta ⏳"
PUBLISH_FAILED = "Uy, Instagram no me dejó publicarlo 🙈 ¿Lo intento de nuevo?"
BRAND_GENERATING = "¡Gracias! Estoy estudiando tu marca, en un minuto te cuento lo que entendí ⏳"
BRAND_FIX_PROMPT = "Contame qué cambio, con tus palabras."
READY_OPEN_CHAT = "¡Listo, ya conozco tu marca! ¿En qué te puedo ayudar hoy?"
REVISING = "Va, lo ajusto ⏳"
RETRYING = "Dale, lo intento de nuevo ⏳"
POST_GENERATING = "¡Dale! Lo armo ⏳"
PUBLISHING = "¡Dale, lo subo! ⏳"
POST_CHANGE_PROMPT = (
    '¿Qué le cambio? Por ejemplo: "más corto", "otra foto", "mencioná el envío gratis".'
)
POST_DISCARDED = "Listo, lo descarto. ¿Querés que haga otro en su lugar?"
# `publish_when_adhoc` without "Programar" until scheduling exists (T30, Should).
PUBLISH_NOW_ASK = "¡Aprobado! ¿Lo publico ya?"
GENERATION_BUSY = "Estoy terminando otro post 🙌 Apenas te lo mande, armamos este."
DAILY_LIMIT = "Por hoy ya armamos todos los diseños que puedo hacer 🙈 Mañana seguimos."
PHOTOS_GONE = "Ya no tengo esas fotos 🙈 ¿Me las mandás de nuevo?"

BUTTON_BRAND_OK = "Sí, es mi marca"
BUTTON_BRAND_FIX = "Corregir algo"
BUTTON_RETRY = "Reintentar"
BUTTON_APPROVE = "Aprobar"
BUTTON_CHANGE = "Cambiar"
BUTTON_DISCARD = "Descartar"
BUTTON_PUBLISH_NOW = "Publicar ahora"
BUTTON_ANOTHER = "Sí, otro"
BUTTON_NO_THANKS = "No, gracias"
BUTTON_MAKE_POST = "Sí, armalo"
BUTTON_KEEP_PHOTO = "No, guardala"
BUTTON_KEEP_PHOTOS = "No, guardalas"


def photo_too_big(max_mb: int) -> str:
    return f"Esa foto es muy pesada 🙈 ¿Me mandás una más liviana? (hasta {max_mb} MB)"


def published(permalink: str) -> str:
    return f"¡Publicado! 🎉 {permalink}"


def carousel_slide(n: int, count: int) -> str:
    return f"{n}/{count}"


def brand_summary(business_name: str, summary: str) -> str:
    return f"Esto es lo que entendí de *{business_name}* 👇\n\n{summary}\n\n¿Es así?"


def post_actions(carousel: bool) -> str:
    """The buttons message after a post's images, until `post_preview` carries them (T19)."""
    return f"👆 ¿Qué hacemos con este {'carrusel' if carousel else 'post'}?"
