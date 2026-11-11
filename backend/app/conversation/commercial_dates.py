"""Uruguayan commercial dates the orchestrator may mention, so it never guesses one.

Source: docs/research/furniture-decor-uruguay.md, "Commercial calendar". Mother's and Father's
Day are left out: the Cámara Nacional de Comercio y Servicios sets them each year and 2027 isn't
confirmed. Add a year-specific date here only after checking it.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
HORIZON_DAYS = 45


@dataclass(frozen=True, slots=True)
class CommercialDate:
    name: str
    month: int
    day: int
    price_led: bool = False


YEARLY = (
    CommercialDate("Reyes", 1, 6),
    CommercialDate("Día de los Abuelos", 6, 19),
    CommercialDate("Navidad", 12, 25),
)


def black_friday(year: int) -> date:
    """The fourth Friday of November."""
    first = date(year, 11, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7 + 21)


def upcoming(today: date, horizon: int = HORIZON_DAYS) -> list[tuple[date, str, bool]]:
    found: list[tuple[date, str, bool]] = []
    for year in (today.year, today.year + 1):
        found += [(date(year, d.month, d.day), d.name, d.price_led) for d in YEARLY]
        found.append((black_friday(year), "Black Friday", True))
    end = today + timedelta(days=horizon)
    return sorted(item for item in found if today <= item[0] <= end)


def render(now: datetime) -> str:
    lines = []
    for when, name, price_led in upcoming(now.date()):
        days = (when - now.date()).days
        line = f"- {WEEKDAYS[when.weekday()]} {when:%d/%m/%Y} (en {days} días): {name}"
        lines.append(line + " (price-led: only if the brand fits)" if price_led else line)
    return "\n".join(lines)
