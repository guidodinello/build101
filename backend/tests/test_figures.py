from app.knowledge.base import BusinessKnowledge, CatalogItem
from app.posts.figures import given_facts, unsupported_figures


def test_a_figure_from_the_brief_is_supported_whatever_its_separators() -> None:
    assert unsupported_figures("Hoy $1.500 y 20% off", "mesa a $1500, 20 % de descuento") == []


def test_prices_percentages_and_promos_not_given_are_listed_once() -> None:
    draft = "2x1 en sillas, 30% off, U$S 90 y 30% off otra vez"
    assert unsupported_figures(draft, "sillas nuevas") == ["2x1", "30%", "U$S 90"]


def test_a_catalog_price_counts_as_given() -> None:
    known = BusinessKnowledge(catalog=[CatalogItem("Mesa", "$ 12.000", "roble")])
    assert unsupported_figures("La mesa sale $12000", given_facts("mesa", known)) == []


def test_plain_numbers_and_dates_are_not_figures() -> None:
    assert unsupported_figures("Abrimos de 10 a 14 desde 2026, 3 modelos", "") == []
