from app.posts.maker import INSTAGRAM_CAPTION_LIMIT, post_text


def test_short_text_is_untouched() -> None:
    assert post_text("Mesa nueva.", ["#muebles", "#uruguay"]) == "Mesa nueva.\n\n#muebles #uruguay"


def test_exactly_at_the_limit_is_untouched() -> None:
    caption = "a" * INSTAGRAM_CAPTION_LIMIT
    assert post_text(caption, []) == caption


def test_long_text_is_cut_at_a_word_within_the_limit() -> None:
    caption = "Hola mundo. " * 400
    text = post_text(caption, ["#muebles"])
    assert len(text) <= INSTAGRAM_CAPTION_LIMIT
    assert text.endswith("…")
    assert not text[:-1].endswith(" ")


def test_unbroken_text_is_still_cut_to_the_limit() -> None:
    text = post_text("a" * 5000, [])
    assert len(text) == INSTAGRAM_CAPTION_LIMIT
