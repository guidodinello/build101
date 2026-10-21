from datetime import date, datetime

from app.conversation import commercial_dates
from app.conversation.turns import context_block


def test_black_friday_is_the_fourth_friday_of_november():
    assert commercial_dates.black_friday(2026) == date(2026, 11, 27)
    assert commercial_dates.black_friday(2027) == date(2027, 11, 26)


def test_only_dates_inside_the_horizon_are_listed():
    found = commercial_dates.upcoming(date(2026, 10, 20))
    assert [name for _, name, _ in found] == ["Black Friday"]
    assert commercial_dates.upcoming(date(2026, 10, 20), horizon=80)[-2][1] == "Navidad"


def test_the_list_wraps_into_next_year():
    names = [name for _, name, _ in commercial_dates.upcoming(date(2026, 12, 20))]
    assert names == ["Navidad", "Reyes"]


def test_render_marks_price_led_dates_and_counts_days():
    text = commercial_dates.render(datetime(2026, 10, 20, 9, 0))
    assert text == (
        "- viernes 27/11/2026 (en 38 días): Black Friday (price-led: only if the brand fits)"
    )


def test_context_block_carries_upcoming_dates_only_when_there_are_any():
    with_dates = context_block([], [], now=datetime(2026, 10, 20, 9, 0))
    assert "<upcoming_dates>" in with_dates
    assert "<upcoming_dates>" not in context_block([], [], now=datetime(2026, 9, 1, 9, 0))
