import re

# Gemini writes Markdown; WhatsApp bold is `*x*` and italic is `_x_`. URLs are split out first so
# permalinks (`https://www.instagram.com/p/AbC__d/`) stay byte-identical.
_URL = re.compile(r"(https?://\S+)")
_BOLD_ITALIC = re.compile(r"\*\*\*(?=\S)([^\n]+?)(?<=\S)\*\*\*")
_BOLD = re.compile(r"\*\*(?=\S)([^\n]+?)(?<=\S)\*\*")
_UNDERSCORE_BOLD = re.compile(r"(?<![\w_])__(?=\S)([^\n]+?)(?<=\S)__(?![\w_])")


def to_whatsapp(text: str) -> str:
    """Markdown `**x**` / `__x__` / `***x***` to WhatsApp `*x*` / `_x_` / `*_x_*`."""
    parts = _URL.split(text)
    # re.split with a capture group puts the URLs at the odd indexes.
    return "".join(part if i % 2 else _convert(part) for i, part in enumerate(parts))


def _convert(text: str) -> str:
    text = _BOLD_ITALIC.sub(r"*_\1_*", text)
    text = _BOLD.sub(r"*\1*", text)
    return _UNDERSCORE_BOLD.sub(r"_\1_", text)
