"""The static input of the Niche Analyst, per niche (ADR 0025, agents.md § Niche Analyst)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Niche:
    id: str
    description: str  # for the prompt, in English
    location: str
    timezone: str  # where the niche's week starts (niche_reports.week_start)
    reference_websites: tuple[str, ...]  # read with url_context; stores to learn from, not copy
    search_themes: tuple[str, ...]  # Google searches, in Spanish


# docs/research/furniture-decor-uruguay.md, "Reference websites" and "Search themes for the
# Niche Analyst". The year is left out of the trends theme (the prompt gives today's date),
# and the two date-bound themes (wedding registries, Mother's Day) are left out:
# commercial dates come from the Content Strategist's static list.
CURATED_WOOD_FURNITURE_UY = Niche(
    id="curated-wood-furniture-uy",
    description=(
        "Curated solid-wood and restored furniture and home stores: noble materials, "
        "timeless design, pieces made to last, sold with advice rather than on price"
    ),
    location="Uruguay (mostly Montevideo)",
    timezone="America/Montevideo",
    reference_websites=(
        "https://www.laiberica.com.uy/",
        "https://kateiuy.lovable.app",
        "https://marvic.com.uy/",
        "https://www.samic.com.uy/",
        "https://disenomontevideo.com.uy/",
        "https://www.laismuebles.com.uy/",
    ),
    search_themes=(
        "muebles madera maciza Uruguay diseño",
        "madera uruguaya muebles a medida eucalipto fresno",
        "cuidado madera maciza muebles consejos",
        "tendencias decoración madera natural materiales nobles",
        "ambientación living madera estilo atemporal",
        "diseño de mobiliario uruguayo",
        "Casa FOA Uruguay",
        "feria Ideas+ diseño",
    ),
)

NICHES = {niche.id: niche for niche in (CURATED_WOOD_FURNITURE_UY,)}
