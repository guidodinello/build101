import pytest

from app.channels.whatsapp_format import to_whatsapp

PERMALINK = "https://www.instagram.com/p/AbC__d/"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("**a**", "*a*"),
        ("__a__", "_a_"),
        ("**a** y **b**", "*a* y *b*"),
        ("**a** y __b__ y **c**", "*a* y _b_ y *c*"),
        ("***a***", "*_a_*"),
        ("**Detalles que enamoran:** mesa", "*Detalles que enamoran:* mesa"),
    ],
)
def test_converts_markdown(text: str, expected: str) -> None:
    assert to_whatsapp(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "*a*",
        "_a_",
        "~a~",
        "hola, sin formato",
        "",
        "2 ** 3 ** 4",
        "foo__bar__baz",
        "snake_case_name y dentro__de__palabra y a__b__",
        "**sin cerrar",
        "**a\nb**",
    ],
)
def test_leaves_valid_or_plain_text_untouched(text: str) -> None:
    assert to_whatsapp(text) == text


def test_urls_stay_byte_identical() -> None:
    text = f"**Mirá** {PERMALINK} y https://x.test/a/**b**/c?q=__z__"

    assert to_whatsapp(text) == f"*Mirá* {PERMALINK} y https://x.test/a/**b**/c?q=__z__"


def test_live_numbered_list() -> None:
    text = (
        "Ideas:\n"
        "1. **Detalles que enamoran:** mostrá la madera\n"
        "2. **Antes y después:** el taller\n"
        f"3. Mirá {PERMALINK}"
    )

    assert to_whatsapp(text) == (
        "Ideas:\n"
        "1. *Detalles que enamoran:* mostrá la madera\n"
        "2. *Antes y después:* el taller\n"
        f"3. Mirá {PERMALINK}"
    )
