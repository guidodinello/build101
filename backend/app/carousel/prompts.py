from .schemas import CarouselBrief, CarouselCopy, SlideRole, TemplateFamily

FIXED_RULES = """Rules:
- Show the real product from the product reference images exactly as it is: keep its shape, \
color, material and proportions. Change only the scene, light and styling around it.
- No text of any kind anywhere in the image: no words, letters, numbers, signs, labels, \
prices, logos or watermarks. The design's text is added afterwards.
- A photograph, not a graphic design: no frames, borders, collages or overlays."""

# Where each template puts the scene, and so what the scene must leave calm (ADR 0028)
FRAMING: dict[tuple[TemplateFamily, SlideRole], str] = {
    ("editorial", "cover"): (
        "Full-bleed vertical 4:5 photo. The headline is set over the lower 40% of the frame, "
        "so keep that area calm and uncluttered (floor, wall, tabletop, soft shadow) and place "
        "the product in the upper-middle part."
    ),
    ("editorial", "content"): (
        "Shown in a nearly square frame above the text: the product centered, with some room "
        "around it."
    ),
    ("editorial", "cta"): (
        "Shown small inside an arch-shaped frame: one clear subject, centered, on a simple "
        "background."
    ),
    ("numbers", "cover"): (
        "Shown inside a tall arch-shaped frame: the product centered, filling the lower two "
        "thirds of the frame."
    ),
    ("numbers", "content"): (
        "Cropped to a wide band at the top of the slide (about 16:9): keep the subject in the "
        "horizontal middle of the frame, nothing important near the top or bottom edge."
    ),
    ("numbers", "cta"): "Shown inside a circle: one centered subject, simple background.",
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
    sections = [
        f"Photo {index} of {len(copy.slides)} for an Instagram carousel ({slide.role} slide).",
        f"Photographic style shared by every photo: {brief.style_prompt}",
        f"This photo shows: {scene_prompt(brief, index)}",
        f"Framing: {framing(brief.family, slide.role)}",
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


def framing(family: TemplateFamily, role: SlideRole) -> str:
    """A one-slide panorama has nothing to span, so it is framed like an editorial slide."""
    return FRAMING.get((family, role)) or FRAMING[("editorial", role)]


def panorama_ratio(count: int) -> str:
    return PANORAMA_RATIOS.get(count, WIDEST_RATIO)


def scene_prompt(brief: CarouselBrief, index: int) -> str:
    for scene in brief.slides:
        if scene.index == index:
            return scene.scene_prompt
    raise ValueError(f"carousel brief has no scene for slide {index}")
