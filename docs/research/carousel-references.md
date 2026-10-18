# Carousel references: structure, copy and design patterns

Analysis of 8 Instagram carousel templates the team picked as references (read 2026-10-17), to define carousels the Agency could generate for a furniture business: informational carousels about the niche (no photos needed) and carousels built from the Catalog.

The references are Canva templates with placeholder brands and stock photos. They are **not committed** to this public repo (third-party design and photos); this doc describes them instead. We take the patterns, not the designs.

## The references

| # | Reference | Slides / size | Topic and tone | Visual family |
|---|---|---|---|---|
| R1 | Corporate grey "how to grow on social media" | 6, 4:5 | Tips, corporate | Photo collage + big sans headline |
| R2 | Yellow/green "habits that changed my life" | 5, 3:4 | Tips, editorial lifestyle | Full-bleed photo + text overlay |
| R3 | Yellow "things I'm relearning" (Notes app) | 6, 4:5 | Personal list | Full-bleed photo + native UI card (iPhone Notes) |
| R4 | Brown/white "how to grow on social media" | 5, 4:5 | Tips, warm editorial | Solid brand color + photo column |
| R5 | Neutral scrapbook "May photo diary" | 5, 4:5 | Monthly recap | Collage, tape/stars, handwriting |
| R6 | Yellow/brown "reading habit tips" | 5, 3:4 | Tips, cozy | Full-bleed photo + bold sans overlay |
| R7 | Brown/cream "things I've learned" | 5, 4:5 | Personal lessons | Photo + serif/script, mixed frames |
| R8 | Black/white "side hustles" | 6, 4:5 | How I do it, minimal | Text on paper, occasional icon or half photo |

Sizes from the PDF page boxes: 810×1012 pt (= 1080×1350, Instagram 4:5) and 810×1080 pt (= 1080×1440, 3:4).

## Structure: three slide types

Every reference is built from the same three slide types:

1. **Cover (hook)**: a 3–6 word title that promises a list or a transformation, a one-line subtitle, and a swipe cue (arrow, "learn more" pill, "4 tips" badge, pagination dots). R1, R4, R6, R8.
2. **Point slide** (one idea per slide, repeated 3–5 times):
   - a **label** with a number (`Habit 01`, `tips 02`, `TIP 03`, `1.`), often in a script or outlined pill;
   - a **title** of 2–5 words in the display font;
   - a **body** of 1–3 short sentences (≈ 90–250 chars);
   - optionally a **takeaway** line set apart (R6, R8).
3. **Closing** (only 3 of 8 have one): follow/save CTA + contact (R1), a question to drive comments (R8), a sign-off (R5). The other five end on the last point, which wastes the slide where Instagram's swipe ends.

**Persistent chrome** on every slide: brand name top-left, handle or year top-right, `SLIDE 0N` and website at the bottom (R1, R2, R4, R6). It makes the slides read as one piece and brands every slide when shared on its own.

Length: 5–6 slides in all eight. Instagram allows up to 20 and longer carousels are reported to get more saves ([instagram-content-trends.md](instagram-content-trends.md#carousels-craft)), but Zernio and the Instagram API publish at most 10 items ([media-uploads.md](media-uploads.md#publishing-video-and-carousels-zernio-instagram)).

## Copy patterns

- **Cover titles**: "How to …", "N things I learned …", "Habits that …", "How I manage …". Promise + number.
- **Point titles** are imperatives or short claims ("Stay consistent", "Keep books within reach", "Healing isn't linear").
- **Voice**: first person ("I say no…", R3, R7, R8) feels personal and handmade; imperative ("Create…", R1, R4, R6) feels like advice. Both fit an Owner speaking for their workshop.
- The body explains *why* in one sentence after the *what*. No prices, no claims that need a source.

## Design patterns

- **Type**: a display serif (often condensed: Times Condensed, Playfair Display, Old Standard, Instrument Serif) or a heavy geometric sans (Montserrat Bold) for titles; a clean sans for body (DM Sans, Public Sans, Gotham, Montserrat); an optional script only for labels (`tips 01`). At most 3 fonts. (Font names from the PDFs' embedded fonts.)
- **Color**: background + text + one accent. Yellow accent over dark photos (R2, R6); brown/cream (R4, R7); off-white paper + black (R8).
- **Hierarchy**: title takes 30–50% of the slide; body is small and short; lots of empty space.
- **Photos are optional**: R8 is almost all text and is the most reusable for niche information. R4 keeps working if the photo column becomes a solid block or a product cut-out.
- **Native/handmade touches** (R3's Notes card, R5's tape and handwriting, R7's script) look less like an ad, which matches the "anti-AI design" trend for handmade products ([instagram-content-trends.md](instagram-content-trends.md#trend-templates-seen-in-october-2026)).

## Four families worth templating

| Family | From | Needs photos? | Best for (furniture) |
|---|---|---|---|
| **Minimal text** | R8 | No (optional icon or half photo) | Niche information: care, measurements, materials, myths |
| **Color block + inset** | R4, R1 | Optional (solid block or pattern without one) | Tips that show the Catalog: "4 mesas para livings chicos" |
| **Photo overlay** | R2, R6, R3 | Yes, one good photo per slide | Lifestyle/ambience with the Owner's own photos |
| **Scrapbook diary** | R5 | Yes, several per slide | Monthly recap: "Octubre en el taller" |

Example carousels for a furniture business:

- Niche info, no photos: "5 errores al elegir un sofá para un living chico", "Cómo cuidar la madera maciza", "Mitos y verdades del melamínico".
- Catalog: "3 mesas que entran en un monoambiente" (one Product per point slide, with its photo if one exists).
- Owner story: "Cosas que aprendimos en 10 años haciendo muebles".
- Recap: "Octubre en el taller" (needs many photos).

## Implications for the Agency

- Written for the template approach of [ADR 0009](../decisions/0009-branded-templates-over-real-photos.md) (the LLM fills slots, the renderer draws), now superseded by AI-generated images ([ADR 0018](../decisions/0018-ai-image-generation-service.md), carousels in [ADR 0022](../decisions/0022-carousels-in-mvp.md)); the slide structure below still applies. A carousel is an ordered list of slides from one **family**, sharing chrome, fonts and palette from the Brand Brain.
- Structured output sketch (cover → N points → closing):

```python
class CarouselSlide(BaseModel):
    kind: Literal["cover", "point", "closing"]
    label: str | None        # "Tip 01"; numbering set in code, not by the model
    title: str               # ≤ 40 chars
    body: str | None         # ≤ 220 chars
    takeaway: str | None     # ≤ 80 chars
    asset_id: str | None     # optional photo
    product_id: str | None   # optional Catalog Product

class CarouselSpec(BaseModel):
    family: Literal["minimal_text", "color_block", "photo_overlay", "scrapbook"]
    slides: list[CarouselSlide]   # 5–10: 1 cover, 3–8 points, 1 closing
```

- Deterministic checks: 5–10 slides (Zernio's cap), exactly one cover and one closing, the number promised on the cover equals the number of point slides, slot lengths, `photo_overlay`/`scrapbook` only when enough `usable` assets exist, ids belong to the Business.
- Always add a closing slide (save/share/comment CTA): most references skip it.
- Informational carousels carry facts (care, measurements, materials). The rule "agents never invent facts" ([AGENTS.md](../../AGENTS.md#building-the-mvp)) needs a decision on what sources they may use; see [open-questions.md](../open-questions.md#carousels).
- Carousels were Won't when this was written; [ADR 0022](../decisions/0022-carousels-in-mvp.md) brought them into the MVP.
