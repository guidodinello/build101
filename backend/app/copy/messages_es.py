"""Fixed owner-facing messages, from docs/product/conversation-design.md (copy deck)."""

STALE_BUTTON = "Ese botón ya no está activo 🙂"
UNSUPPORTED_MEDIA = (
    "Por ahora solo entiendo texto, audios, fotos y videos 🙏 ¿Me lo escribís o me mandás un audio?"
)
AUDIO_UNCLEAR = "No te llegué a entender el audio 🙈 ¿Me lo mandás de nuevo o me lo escribís?"
REPLY_FAILED = "Uy, se me trabó algo. ¿Me lo mandás de nuevo en un ratito?"
# Until photos are stored as Brand assets (F1.5), so `photo_saved` would promise too much.
PHOTO_NOT_SAVED_YET = "¡Buenísima la foto! 📸 Todavía no puedo guardarla, pero muy pronto sí."
