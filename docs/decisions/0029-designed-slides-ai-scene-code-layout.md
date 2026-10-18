# 0029: Designed slides: the AI makes the scene, code templates make the layout

- Date: 2026-10-18
- Status: proposed

## Context

Designed posts look generic: the image model paints a headline and a body over a photo. The slide spec has only those two text slots, the design system is one free-text `style_prompt`, slides are anchored on the cover through a "style reference" that `gemini-nano-banana-2.1` has no slot for, nothing crosses a slide border, and the logo is stamped in a fixed corner ([ADR 0027](0027-owner-logo-stamped-in-code.md)). Every image model's own docs still say exact text placement is unreliable, which is why [ADR 0022](0022-carousels-in-mvp.md) needed a Text Checker. The diagnosis and the options (better prompts only, own renderer, hosted template API, model-rendered type plus Ideogram Layerize) are in [research/post-design/recommendation.md](../research/post-design/recommendation.md).

This revises [ADR 0018](0018-ai-image-generation-service.md) ("the backend never composes images") and [ADR 0022](0022-carousels-in-mvp.md) (text rendered by the image model), and changes where [ADR 0027](0027-owner-logo-stamped-in-code.md) places the logo.

## Decision

- **Gemini makes only text-free scenes.** The "no text in the image" rule of ADR 0018 applies to every image again. The prompt asks for the calm area each template needs for its text.
- **Code templates make every designed slide.** The Art Director picks a template **family**; each slide has a role (cover, content, cta), a short kicker, a headline and an optional body. Numbering, page counter, swipe cue, the brand mark and the fixed Spanish chrome ("Deslizá", "Guardalo") come from the template, not from the model.
- **The renderer is Takumi** (`takumi-js`, MIT or Apache-2.0) in a Node route handler of the Next.js app on Vercel: `POST /api/render` takes one slide's spec, the scene and the logo as data URIs, and returns a 1080 × 1350 JPEG. The backend calls it once per slide, in parallel, with a shared secret. No Chromium anywhere ([renderers.md](../research/post-design/renderers.md)).
- **Three families first**: `editorial` (magazine, serif), `numbers` (numbered guide, bold grotesque, a timeline and circles that cross the slide seams) and `panorama` (one wide scene sliced into slides, with a line that runs across them). Fonts are OFL files committed with the renderer; icons are Lucide (ISC).
- **Panorama is one wide generation**: `4:1` at 4K for 4–5 slides, `8:1` for 6–10, `16:9` for 2 and `21:9` for 3, cropped to N × 4:5 and sliced in the backend.
- **The logo goes in the template's brand mark**, still the Owner's original file and only when the Owner asks (`with_logo`). The backend sends whether the logo is light or dark, and the template puts it on a chip when it would blend in. Image Posts made of photos as they are keep the ADR 0027 corner stamp.
- **The Text Checker is dropped**: code sets the text, so it can't be misspelled.

## Consequences

- Text is always exact and legible, and slides of a carousel share one layout system. Variety comes from the number of families, so adding families is ongoing design work.
- A second service in the post path: the backend needs `RENDERER=takumi`, `RENDERER_URL` and `RENDERER_SECRET`, and the frontend `RENDER_SECRET`. A Vercel outage or a cold start now delays posts. `RENDERER=mock` returns the scene unchanged, for tests and local runs without the frontend.
- Requests carry images as base64, so each one stays well under Vercel's 4.5 MB body limit only because the scene is resized to 1080 × 1350 first.
- The Brand Brain has no fonts or Instagram handle yet; families pick their own fonts, and the brand mark is the logo or the business name.
- A panorama costs one 4K image ($0.113) instead of one 2K image per slide; product fidelity across a wide frame is untested.
- Slide redo regenerates the scene and re-renders the slide; it no longer depends on the cover for the text style.
