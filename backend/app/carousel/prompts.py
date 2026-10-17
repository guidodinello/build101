from .schemas import CarouselBrief, CarouselCopy, SlideCopy, TextCheck

FIXED_RULES = """Rules:
- Show the real product from the product reference images exactly as it is: keep its shape, \
color, material and proportions. Change only the scene, light and styling around it.
- The only text in the image is the text quoted above, spelled exactly as given, accents \
included. Do not add any other words, letters, numbers, prices, discounts, dates, slogans \
or watermarks.
- Do not draw, invent or alter any logo.
- Keep all text inside the central 90% of the image, clear of the edges.
- Vertical 4:5 Instagram carousel slide."""

ANCHOR_INSTRUCTION = (
    "The style reference image is another slide of this same carousel. Match its typography, "
    "color palette, layout grid and lighting so both slides read as one set. Do not copy its "
    "scene or its text."
)

BLOCKED_RETRY_NOTE = (
    "Keep the scene simple and focused on the product, in a neutral, everyday setting."
)


def build_slide_prompt(
    brief: CarouselBrief, copy: CarouselCopy, index: int, *, anchored: bool
) -> str:
    slide = copy.slides[index - 1]
    sections = [
        f"Slide {index} of {len(copy.slides)} of an Instagram carousel ({slide.role} slide).",
        f"Visual system shared by every slide: {brief.style_prompt}",
        f"This slide shows: {scene_prompt(brief, index)}",
        text_instruction(slide),
    ]
    if anchored:
        sections.append(ANCHOR_INSTRUCTION)
    sections.append(FIXED_RULES)
    return "\n\n".join(sections)


def scene_prompt(brief: CarouselBrief, index: int) -> str:
    for scene in brief.slides:
        if scene.index == index:
            return scene.scene_prompt
    raise ValueError(f"carousel brief has no scene for slide {index}")


def text_instruction(slide: SlideCopy) -> str:
    lines = [f'Headline: "{slide.headline}"']
    if slide.body:
        lines.append(f'Body: "{slide.body}"')
    return "Render exactly this text and no other text:\n" + "\n".join(lines)


def text_retry_note(check: TextCheck) -> str:
    issues = "; ".join(check.issues) or f'it rendered "{check.found}"'
    return (
        f"The previous attempt got the text wrong ({issues}). Spell every word exactly as "
        "quoted, letter by letter, accents included."
    )
