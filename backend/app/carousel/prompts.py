from typing import Literal, assert_never

from .schemas import CarouselBrief, CarouselCopy, Layout, SlideRole, SlideScene, TemplateFamily

# What the renderer draws: a requested layout, or one a family picks per role
ResolvedLayout = Layout | SlideRole | Literal["circle", "window-content"]

FIXED_RULES = """Rules:
- Show the real product from the product reference images exactly as it is: keep its shape, \
color, material and proportions. Change only the scene, light and styling around it.
- No text of any kind anywhere in the image: no words, letters, numbers, signs, labels, \
prices, logos or watermarks. The design's text is added afterwards.
- A photograph, not a graphic design: no frames, borders, collages or overlays."""

CALM_BACKGROUND = "one clear subject, centered, on a simple, uncluttered background"

# Where each layout shows the scene, and so what the 4:5 photo must leave calm or keep away from
# the crop (ADR 0029, ADR 0035). Keys are the layouts each family resolves to, as in
# frontend/lib/post-render/families/*.tsx.
FRAMING: dict[tuple[TemplateFamily, ResolvedLayout], str] = {
    ("editorial", "overlay"): (
        "Full-bleed vertical 4:5 photo. The headline is set over the lower 40% of the frame, "
        "so keep that area calm and uncluttered (floor, wall, tabletop, soft shadow) and place "
        "the product in the upper-middle part."
    ),
    ("editorial", "frame"): (
        "Shown in a wide frame cropped from the middle of the photo (about 4:3): keep the "
        "product in the vertical middle, nothing important near the top or bottom edge."
    ),
    ("editorial", "photo-top"): (
        "Cropped to a wide band (about 3:2) from the middle of the photo: keep the product in the "
        "horizontal middle band, with some room around it."
    ),
    ("editorial", "full-bleed"): (
        "Full-bleed vertical 4:5 photo with a text card over the lower 45%: keep the product in "
        "the upper half of the frame."
    ),
    ("editorial", "quote"): f"Shown small, in a portrait thumbnail: {CALM_BACKGROUND}.",
    ("editorial", "card"): f"Shown inside an arch-shaped portrait frame: {CALM_BACKGROUND}.",
    ("numbers", "poster"): (
        "Shown inside a tall arch-shaped frame: the product centered, filling the lower two "
        "thirds of the frame."
    ),
    ("numbers", "band"): (
        "Cropped to a wide band at the top of the slide (about 16:10): keep the subject in the "
        "horizontal middle of the frame, nothing important near the top or bottom edge."
    ),
    ("numbers", "split"): (
        "Cropped to a tall, narrow column (about 1:2.8) from the center of the photo: a vertical "
        "composition with the product in the middle third, left to right."
    ),
    ("numbers", "circle"): f"Shown inside a circle: {CALM_BACKGROUND}.",
    ("minimal", "window"): (
        "Shown in a clean portrait window (about 6:7): the product centered with generous "
        "breathing room and a quiet, single-color background."
    ),
    ("minimal", "type"): f"Shown small, inside a circle: {CALM_BACKGROUND}.",
    ("minimal", "window-content"): (
        "Cropped to a square from the middle of the photo: the product centered with breathing "
        "room, quiet background."
    ),
    ("minimal", "side"): (
        "Cropped to a tall half-width column (about 1:2.7): a vertical composition with the "
        "product in the middle third, left to right."
    ),
    ("minimal", "cta"): f"Shown inside a circle: {CALM_BACKGROUND}.",
    ("notes", "card"): (
        "Shown blurred behind a text card, and on the cover as a wide strip (about 2.3:1) cut "
        "from the middle: soft light and pleasant color, the product in the horizontal middle "
        "band."
    ),
    ("notes", "checklist"): (
        "Shown only blurred behind a text card: soft light, pleasant color, no busy detail."
    ),
    ("notes", "cta"): "Shown only blurred behind a text card: soft light, pleasant color.",
    ("scrapbook", "polaroid"): (
        "Shown as a nearly square instant photo: the product centered, candid and natural, "
        "like a real snapshot."
    ),
    ("scrapbook", "taped"): (
        "Cropped to a wide print (about 3:2) from the middle of the photo: the product in the "
        "horizontal middle band, candid and natural."
    ),
    ("scrapbook", "cta"): "Shown as a nearly square instant photo: the product centered.",
}

ANCHOR_INSTRUCTION = (
    'The image labelled "Another slide of this carousel" is a photo from the same set. Match '
    "its lighting, color palette and photographic style so the photos read as one series. Do "
    "not copy its scene or its framing."
)

BLOCKED_RETRY_NOTE = (
    "Keep the scene simple and focused on the product, in a neutral, everyday setting."
)

PANORAMA_FRAMING = (
    "The wide image is cut into {count} equal vertical panels, shown one after another as the "
    "slides of a carousel. The scene must flow continuously across the panel borders: the same "
    "room, the same horizon or floor line, the same light, with no visible seams. Keep the "
    "main subject of each panel away from the panel borders. Keep the top 45% of every panel "
    "calm (plain wall, ceiling, sky or soft light): text is set over it afterwards."
)

# Gemini's ratio closest to N side-by-side 4:5 slides (0.8 N : 1), cropped afterwards
PANORAMA_RATIOS = {2: "16:9", 3: "21:9", 4: "4:1", 5: "4:1"}
WIDEST_RATIO = "8:1"


def build_slide_prompt(
    brief: CarouselBrief, copy: CarouselCopy, index: int, *, anchored: bool
) -> str:
    slide = copy.slides[index - 1]
    layout = resolved_layout(brief.family, slide.role, scene(brief, index).layout, slide.items)
    sections = [
        f"Photo {index} of {len(copy.slides)} for an Instagram carousel ({slide.role} slide).",
        f"Photographic style shared by every photo: {brief.style_prompt}",
        f"This photo shows: {scene_prompt(brief, index)}",
        f"Framing: {framing(brief.family, layout)}",
    ]
    if anchored:
        sections.append(ANCHOR_INSTRUCTION)
    sections.append(FIXED_RULES)
    return "\n\n".join(sections)


def build_panorama_prompt(brief: CarouselBrief, copy: CarouselCopy) -> str:
    count = len(copy.slides)
    panels = "\n".join(
        f"- Panel {index}: {scene_prompt(brief, index)}" for index in range(1, count + 1)
    )
    sections = [
        "One continuous wide panoramic photo for a seamless Instagram carousel.",
        f"Photographic style: {brief.style_prompt}",
        PANORAMA_FRAMING.format(count=count),
        f"From left to right:\n{panels}",
        FIXED_RULES,
    ]
    return "\n\n".join(sections)


CTA_LAYOUTS: dict[TemplateFamily, ResolvedLayout] = {"editorial": "card", "numbers": "circle"}


def resolved_layout(
    family: TemplateFamily, role: SlideRole, layout: Layout, items: list[str]
) -> ResolvedLayout:
    """The layout the renderer draws (frontend/lib/post-render/families/*.tsx resolve the same)."""
    match family, role:
        case "panorama", _:
            return role
        case _, "cta":
            return CTA_LAYOUTS.get(family, "cta")
        case "editorial", "cover":
            return "frame" if layout == "frame" else "overlay"
        case "editorial", _:
            return layout if layout in ("full-bleed", "quote") else "photo-top"
        case "numbers", "cover":
            return "poster"
        case "numbers", _:
            return "split" if layout == "split" else "band"
        case "minimal", "cover":
            return "type" if layout == "type" else "window"
        case "minimal", _:
            return "side" if layout == "side" else "window-content"
        case "notes", "content" if layout == "checklist" or (layout == "auto" and items):
            return "checklist"
        case "notes", _:
            return "card"
        case "scrapbook", "content" if layout == "taped":
            return "taped"
        case "scrapbook", _:
            return "polaroid"
        case _:
            assert_never(family)


def framing(family: TemplateFamily, layout: ResolvedLayout) -> str:
    """A one-slide panorama has nothing to span, so it is framed like an editorial cover."""
    if family == "panorama":
        return FRAMING[("editorial", "overlay")]
    return FRAMING.get((family, layout)) or FRAMING[("editorial", "overlay")]


def panorama_ratio(count: int) -> str:
    return PANORAMA_RATIOS.get(count, WIDEST_RATIO)


def scene(brief: CarouselBrief, index: int) -> SlideScene:
    for slide in brief.slides:
        if slide.index == index:
            return slide
    raise ValueError(f"carousel brief has no scene for slide {index}")


def scene_prompt(brief: CarouselBrief, index: int) -> str:
    return scene(brief, index).scene_prompt
