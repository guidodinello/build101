"""Fixed owner-facing text, from docs/product/conversation-design.md (copy deck).

The orchestrator writes what the Owner reads (ADR 0026): code emits an event
(`app/conversation/events.py`) and the model answers it with the conversation in view. So this
module holds only:

- fallbacks for when the LLM is unavailable: `REPLY_FAILED`, `STILL_WORKING`, `LOOKING_AT_PHOTOS`
  and the text of each event (`events.fallback`), sent only if that event's turn fails;
- verbatim events, sent as written without a model turn (`events.verbatim`): `brand_summary`,
  `JOB_FAILED` for a failed job and `BRAND_GENERATING`;
- text sent directly, outside the chat: Flow 1 before the web form (`welcome`, `name_ack_link`,
  `link_reminder`, the `OnboardingGate`, an exception recorded in ADR 0026), and `waitlist` to a
  number not on the pilot list (the `PilotGate`, #186);
- labels, not conversation: `carousel_slide`.
"""

STALE_BUTTON = "Ese botón ya no está activo 🙂"
UNSUPPORTED_MEDIA = (
    "Por ahora solo entiendo texto, audios, fotos y videos 🙏 ¿Me lo escribís o me mandás un audio?"
)
AUDIO_UNCLEAR = "No te llegué a entender el audio 🙈 ¿Me lo mandás de nuevo o me lo escribís?"
REPLY_FAILED = "Uy, se me trabó algo. ¿Me lo mandás de nuevo en un ratito?"
STILL_WORKING = "Un segundo, ya te respondo ⏳"
RATE_LIMITED = "Me llegaron muchos mensajes juntos 🙈 Dame un minuto y seguimos."
LOOKING_AT_PHOTOS = "Estoy mirando las fotos, ya te digo 👀"
JOB_FAILED = "Uy, se me trabó algo armando esto. ¿Lo intento de nuevo?"
# `photo_saved` without its buttons (T18) and without "la guardo para próximos posts": until
# T02 a photo is only kept for 30 minutes.
PHOTO_KEPT = "¡Buenísima! 📸 ¿Armo un post con esta foto?"
PHOTOS_KEPT = "¡Buenísimas! 📸 ¿Armo un post con estas fotos?"
PHOTO_UNREADABLE = "No pude abrir la foto 🙈 ¿Me la mandás de nuevo?"
# Over the megapixel cap, not the MB one: the same photo again would fail the same way.
PHOTO_TOO_LARGE = "Esa foto es demasiado grande 🙈 ¿Me mandás una más chica?"
PUBLISH_PENDING = "Instagram lo está procesando, en un ratito aparece en tu cuenta ⏳"
PUBLISH_FAILED = "Uy, Instagram no me dejó publicarlo 🙈 ¿Lo intento de nuevo?"
NEED_IG = "Todavía no puedo publicar en tu Instagram, falta conectarlo de nuestro lado 🙈"
BRAND_GENERATING = "¡Gracias! Estoy estudiando tu marca, en un minuto te cuento lo que entendí ⏳"
BRAND_FIX_PROMPT = "Contame qué cambio, con tus palabras."
READY_OPEN_CHAT = "¡Listo, ya conozco tu marca! ¿En qué te puedo ayudar hoy?"
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
VIDEO_ACTIONS = "👆 ¿Te gusta el video? ¿Lo subo o le cambio algo?"
VIDEO_FAILED = (
    "Uy, no me salió el video 🙈 El post sigue como estaba. ¿Probamos de nuevo más tarde?"
)
VIDEO_BLOCKED = "No pude hacer un video con esa foto 🙈 El post sigue como estaba."
VIDEO_DAILY_LIMIT = "Por hoy ya hicimos todos los videos que puedo 🙈 Mañana seguimos."

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


def welcome(assistant_name: str) -> str:
    return (
        f"¡Hola! 👋 Soy {assistant_name}, tu agencia de marketing en WhatsApp. Te ayudo a "
        "planear, crear y publicar contenido para tus redes, y *nada se publica sin que vos lo "
        "apruebes*. ¿Cómo se llama tu negocio?"
    )


def waitlist(assistant_name: str) -> str:
    return (
        f"¡Hola! 👋 Gracias por escribirnos. {assistant_name} está en un piloto cerrado con pocos "
        "negocios. Cuando abramos más lugares lo vas a ver en nuestra web."
    )


def name_ack_link(business_name: str, url: str) -> str:
    return (
        f"¡Buenísimo, {business_name}! Para conocer tu marca necesito unos datos y algunas "
        f"fotos. Son 5 minutos desde el celu 👇 {url}"
    )


def link_reminder(url: str) -> str:
    return f"Para arrancar me falta que completes esto (5 min) 👇 {url}"


def photo_too_big(max_mb: int) -> str:
    return f"Esa foto es muy pesada 🙈 ¿Me mandás una más liviana? (hasta {max_mb} MB)"


def published(permalink: str) -> str:
    return f"¡Publicado! 🎉 {permalink}"


def carousel_slide(n: int, count: int) -> str:
    return f"{n}/{count}"


def brand_summary(business_name: str, summary: str) -> str:
    return f"Esto es lo que entendí de *{business_name}* 👇\n\n{summary}\n\n¿Es así?"


def post_actions() -> str:
    """The post's buttons message when the model's own follow-up (#31) is not available."""
    return "👆 ¿Te gusta? ¿Lo subo o le cambio algo?"
