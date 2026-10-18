# Better post and carousel designs: diagnosis and recommendation

Research done 2026-10-18. The evidence behind each claim is in the sibling docs: [design-patterns.md](design-patterns.md), [image-models.md](image-models.md), [renderers.md](renderers.md) and [template-apis.md](template-apis.md).

## Diagnosis: why the designs look generic

The current pipeline ([ADR 0018](../../decisions/0018-ai-image-generation-service.md), [ADR 0022](../../decisions/0022-carousels-in-mvp.md), [ADR 0027](../../decisions/0027-owner-logo-stamped-in-code.md)) asks the image model to be the designer, and gives it almost nothing to design with:

1. **The slide spec has two text slots.** `SlideCopy` is a `headline` (at most 6 words) and an optional `body` (at most 20 words) (`backend/app/carousel/schemas.py`, `backend/app/posts/prompts/draft.md`). There is no numbered label, callout, list, big number, CTA button, swipe cue or page counter, so the model can only paint "title + paragraph over a photo".
2. **Layout is a free-text sentence.** `style_prompt` ("palette with hex colors, typography, where the text sits, light") is the whole design system. There are no layouts to pick from, no grid, no fonts named, and no figures (icons, shapes, stickers, arrows). Google's own guidance for design-like output asks for the quoted text, a named font per line and the hierarchy line by line ([image-models.md](image-models.md#prompting-for-design-like-output)), and the prompt gives none of that.
3. **The slides don't share a design, they share a hint.** The other slides get the cover as a "Style reference" (`backend/app/imagegen/gemini.py`). `gemini-nano-banana-2.1` has **no style-reference slot**: it takes 10 object and 4 character references only, and style references exist on Nano Banana Pro ([image-models.md](image-models.md#gemini-nano-banana-21)). So the cover is most likely treated as one more product reference.
4. **Nothing crosses a slide border.** Every slide is a separate generation, so a connected carousel (an element or scene continuing into the next slide) can't happen.
5. **The logo sits on top of the design, not inside it.** It is stamped in a fixed bottom-right corner, and the prompt only asks the model to leave that corner free ([ADR 0027](../../decisions/0027-owner-logo-stamped-in-code.md)).
6. **The Brand Brain has no typography.** `VisualIdentity` has five colors, the logo and `photo_style` (`backend/app/agents/schemas.py`), and no fonts or Instagram handle for persistent brand chrome.
7. **Text in pixels stays a risk.** Every vendor still says their models struggle with exact text placement and spelling ([image-models.md](image-models.md)), which is why ADR 0022 needed a Text Checker and a regeneration.

## What "better" means

From [design-patterns.md](design-patterns.md):

- **Template families** that look current and suit furniture: editorial/magazine with serif type, expressive minimalism, moodboard/scrapbook, shop-the-look, before/after, big numbers, notes-style tips.
- **Slide anatomy**: a hook cover with a swipe cue, numbered labels, one idea per slide, page counter, persistent brand chrome (logo, handle), and a CTA closing slide.
- **Figures**: icons, arrows, dimension lines, numbered dots, tape and stickers, price tags, swatches.
- **Connected carousels**: one N × 1080 px canvas sliced into 1080 × 1350 slides, with elements and lines crossing the seams.
- **Platform limits**: 4:5 (1080 × 1350) is the tallest the API publishes (3:4 is rejected), at most 10 items, JPEG only; the profile grid shows the cover cropped to 3:4 (about 1012 px wide), so the cover must work in its center.

## Options

| | A. Better prompts only | B. AI visual + code layout, own renderer | C. AI visual + hosted template API | D. AI type, then Layerize |
|---|---|---|---|---|
| How | Richer spec and prompts, Nano Banana Pro for style references | The model makes text-free scenes; a template renderer draws text, figures, logo and chrome | Same split, templates built in Templated.io / Orshot / Canva | The model renders type; Ideogram Layerize recovers a clean background plus editable text boxes |
| Layout and type quality | Still model-dependent, varies per slide | Deterministic, designer-defined | Deterministic, designer-defined in a visual editor | Model-dependent, then fixable |
| Connected carousels | Wide image possible, text unreliable across seams | Yes: any canvas width, elements cross seams | Limited: canvas caps of 3840–5000 px (3–4 slides) | Partial |
| Text correctness | Needs the Text Checker | Exact, no check needed | Exact | Exact after layerize |
| Cost per 5-slide carousel | ~$0.67 on Pro (5 × $0.134) | ~$0.11–0.25 of image generation; rendering ~free | Same images + 5 credits (~$0.03–0.15) | Images + layerize calls (price unverified) |
| Engineering | Small | Medium: renderer + templates | Small-medium: API client + templates in a vendor editor | Medium, two providers |
| Lock-in | Gemini | None | Vendor holds the templates | Two vendors |

## Recommendation: B, AI makes the visual and code makes the layout

Split the work the way a designer would: **the image model makes the photography, our templates make the design.**

1. **Art Director picks the design, it doesn't describe it.** It returns a structured spec: a template `family`, a `layout` per slide from that family's catalog, the slots each layout has (label, headline, body, items, big number, callouts, CTA), allowed `figures` (icon names from a set we ship, stickers), and a text-free `scene_prompt` that says where the layout needs negative space. Numbering, page counters, swipe cue and brand chrome are added by code, not by the model. This is the [carousel-references](../carousel-references.md#implications-for-the-agency) spec sketch, extended.
2. **Gemini generates only text-free visuals.** The "no text in the image" rule of ADR 0018 applies again to every image. Two modes:
   - **Per slide**: one scene per slide, as today, each prompted with the negative space its layout needs.
   - **Panorama** for connected carousels: one wide 4K image sliced into slides. `4:1` is exactly 5 slides of 4:5 and `8:1` exactly 10 (4K = 8192 × 2048 and 12288 × 1536); other counts crop the nearest ratio. One 4K image ($0.113) costs less than five 2K slides ($0.25), and 2.1 fixed tiling artifacts on these ratios ([image-models.md](image-models.md#seamless-carousels-from-one-wide-image)).
3. **A template renderer composes each slide.** Templates are React components (JSX + CSS) rendered by **Takumi** (`takumi-js`, MIT/Apache-2.0) in a Node route handler of the Next.js app on Vercel, with no Chromium ([renderers.md](renderers.md#takumi)). Takumi supports grid, flexbox, `z-index`, blend modes, stylesheets, `line-clamp`, balanced wrapping and WOFF2, and outputs JPEG directly. Fonts are OFL Google Fonts pairs; icons come from Lucide (already a frontend dependency, ISC) and Phosphor/Tabler (MIT); stickers, tape, price tags and dimension lines are our own SVGs.
4. **Connected carousels are drawn on one canvas.** The renderer lays out the whole N × 1080 canvas (the panorama or the slides' scenes side by side, plus spanning elements: a line, a cut-out over the seam, an arrow) and renders slide *i* as that canvas shifted by `−i × 1080 px`, so every response stays one 1080 × 1350 JPEG (Vercel caps responses at 4.5 MB).
5. **The logo becomes part of the layout.** Each layout has a logo slot in its brand chrome, still the Owner's original file, never drawn by the model (ADR 0027 keeps holding on that), but placed and sized by the template, with the existing contrast backing logic moved into it.
6. **The Text Checker goes away.** The text is set in code, so it can't be misspelled, and ADR 0022's only vision call and its regeneration round disappear (less cost and less wait).

Why not C as the main path: per-slide credits, templates locked in a vendor's editor, canvas caps that break panoramas over 3–4 slides, async/webhook plumbing and expiring output URLs ([template-apis.md](template-apis.md#hosted-vs-our-own-renderer)). It is the fallback if the Takumi spike fails, or if a designer on the team wants to work in Canva: **Templated.io** (multi-page templates, Canva import, synchronous ~2 s renders, from $29/month) or **Orshot** (multi-page, Figma and Canva import, Python SDK, from $39/month). Keep the slide spec independent of the renderer so switching stays cheap.

Why not only A: it's the cheapest change and some of it is worth doing anyway (name fonts and hierarchy, protect the 1012 px cover center), but the output stays as consistent as the model is on each call, and the model still can't place a real logo, real icons or exact numbers.

### Pipeline

```text
Owner request + photos
  → Copywriter + Art Director (one structured call, as today)
      → DesignSpec: family, slides[{layout, slots, figures, scene_prompt}], panorama?: bool
  → Gemini: text-free scenes (per slide) or one wide panorama (4:1 / 8:1, 4K)
  → backend uploads scenes + logo to Storage (signed URLs)
  → POST frontend /api/render  {spec, brand tokens, image URLs, slide index}  × N in parallel
      ← 1080×1350 JPEG per slide
  → WhatsApp preview → Approval (ADR 0007) → Zernio
```

### Cut-outs (needed for 3 of the 9 families)

Spec-sheet, shop-the-look and colorway families put the product on a solid background with a shadow, which needs a transparent cut-out. Gemini can't output transparency ([image-models.md](image-models.md#layered-and-transparent-output)). Options: Recraft's remove-background endpoint ($0.01), or Ideogram 4.5 / OpenAI with transparent backgrounds. Avoid rembg's default model, whose weights are CC BY-NC (non-commercial) ([design-patterns.md](design-patterns.md#figures-icons-and-asset-licenses)). Start with the families that need only photos.

## What it changes

Recorded in [ADR 0028](../../decisions/0028-designed-slides-ai-scene-code-layout.md) (proposed). It revises:

- [ADR 0018](../../decisions/0018-ai-image-generation-service.md): "the backend never composes images" becomes "a renderer composes the final slide over the AI visual". It doesn't bring back ADR 0009's Chromium: Takumi runs on Vercel, and the Railway container stays small.
- [ADR 0022](../../decisions/0022-carousels-in-mvp.md): text moves from the image model to the templates; anchoring on the cover and the Text Checker are replaced by a shared template family (and the panorama mode); slide redo regenerates the scene and re-renders.
- [ADR 0027](../../decisions/0027-owner-logo-stamped-in-code.md): the logo is still the original file placed in code, but by the layout, not in a fixed corner.
- The Brand Brain gains typography (a font pair from a curated list) and the Instagram handle for brand chrome.
- [post-templates.md](../../design/post-templates.md) (ADR 0009's catalog) is the starting point for the template catalog, with the families in [design-patterns.md](design-patterns.md#template-families-for-furniture).

## Spikes before committing

1. **Takumi on Vercel**: one editorial template (photo + serif headline + label + logo + counter) rendered from a Next.js route; check the output against the browser, the render time, and the Hobby plan's function limits.
2. **Gemini panorama**: one `4:1` 4K generation with the demo business's product photos; check that the product stays faithful across the wide frame and that negative space lands where asked.
3. **Layout-aware scene prompts**: does Gemini keep the requested area (e.g. "top 40% plain wall") empty reliably enough for text to sit on it? Measure on 10 generations.
4. **Fallback check**: the same template rebuilt in Templated.io from a Canva design, to compare quality and effort.

## Open questions

- Which template families ship first? Proposal: editorial, numbers guide and panorama (photos only), then before/after and notes; the cut-out families after a cut-out provider is chosen.
- Does the Owner choose the family ("hacelo tipo revista"), or does the Art Director always choose from the brief and the Niche Report?
- Font pairs: how many curated pairs, and how the wizard maps a brand to one.
- Does the logo go on every designed post by default now that it's part of the layout (today `with_logo` defaults to false)?
- Does the Railway backend call the Vercel renderer directly (shared secret), or does the renderer pull the spec from Supabase?
