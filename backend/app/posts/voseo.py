import re

# Forms that are tuteo only: "tenés" is the voseo of "tienes", so a stem or an ending that both
# share (casas, tu) is not listed.
TUTEO = (
    "tú|tienes|puedes|quieres|necesitas|eres|vienes|haces|sabes|prefieres|piensas|"
    "contigo|ven|haz|pon"
)
TUTEO_PATTERN = re.compile(rf"(?<!\w)({TUTEO})(?!\w)", re.IGNORECASE)


def tuteo_forms(*texts: str) -> list[str]:
    """The tuteo words in the texts, in order and without repeats, lowercased."""
    found = (match.lower() for text in texts for match in TUTEO_PATTERN.findall(text))
    return list(dict.fromkeys(found))
