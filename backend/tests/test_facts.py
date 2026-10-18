from app.posts.facts import drop_unsupported_figures, figures


def test_figures_read_prices_percentages_years_and_dates() -> None:
    text = "Mesa a $1.500, 20% off, desde 2019, hasta el 15/11."
    assert figures(text) == {"1500", "20", "2019", "1511"}


def test_plain_numbers_are_not_figures() -> None:
    assert figures("Una mesa con 4 sillas y 2 estantes") == set()


def test_a_sentence_with_an_invented_price_is_dropped() -> None:
    caption = "Mesa de roble a medida. Hoy a $4.900 nomás. ¿Te la mostramos?"
    assert drop_unsupported_figures(caption, "mesa de roble") == (
        "Mesa de roble a medida. ¿Te la mostramos?"
    )


def test_a_figure_from_the_brief_is_kept_however_it_is_written() -> None:
    caption = "Mesa de roble a $4.900. Escribinos."
    assert drop_unsupported_figures(caption, "precio $4900") == caption


def test_a_figure_from_the_brand_brain_is_kept() -> None:
    caption = "Hacemos muebles desde 2015."
    assert (
        drop_unsupported_figures(caption, "una mesa", '{"about": "taller desde 2015"}') == caption
    )


def test_paragraphs_survive() -> None:
    caption = "Hola.\n\nMesa nueva con 30% de descuento.\n\n¿Querés verla?"
    assert drop_unsupported_figures(caption, "") == "Hola.\n\n¿Querés verla?"
