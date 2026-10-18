# Design patterns for posts and carousels (2025–2026)

What designed Instagram posts and carousels look like now, turned into buildable patterns for a furniture and home decor business. All sources read 2026-10-18. Labels: **official** (Meta docs), **data** (surveys, search data, measured studies), **vendor** (blogs and opinion from companies selling tools or services), **press**.

The structure and copy of carousels is in [carousel-references.md](../carousel-references.md); this doc adds the visual side.

## Platform limits

- **Images**: JPEG only, at most 8 MB, sRGB; aspect ratio between 4:5 and 1.91:1; width 320 to 1440 px, wider is scaled down. Official: [content publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing), [IG user media](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media).
- **Carousels**: at most 10 items through the API, and every item is cropped to the first one's ratio (same sources). The app allows 20, the API doesn't (vendor: [Storrito](https://storrito.com/resources/how-instagrams-20-slide-carousels-work-and-what-the-new-limits-are/)).
- **So 4:5 at 1080 × 1350 is the tallest we can publish.** The in-app 3:4 upload (May 2025, vendor: [Neal Schaffer](https://nealschaffer.com/instagram-post-size/)) is not accepted by the API. 1440 × 1800 is within spec if we want more sharpness.
- **The profile grid is 3:4 since January 2025** (press: [RouteNote, 2025-01-20](https://routenote.com/blog/instagrams-new-profile-grid-layout-from-squares-to-rectangles/)). A 4:5 post shows as a 1012 × 1350 thumbnail: about 34 px cut from each side (vendor: [Planoly](https://planoly.com/blog/guide-to-instagrams-new-vertical-grid)). Only slide 1 appears in the grid (vendor: [socialk.it](https://socialk.it/en/sizes/instagram-carousel-size)), so the cover's key content lives in the central 1012 px.

## Seamless (connected) carousels

- **How they're built**: one canvas of 1080 × N px by 1350 px, guides every 1080 px, sliced into equal slides; every slide the same size or the seam jumps (vendor: [Krumzi, updated 2026-09-03](https://www.krumzi.com/blog/seamless-instagram-carousel), [RFG Creative](https://rfgcreative.com/misc/how-to-create-seamless-instagram-carousel.html)).
- **Seams**: Instagram shows a small gap while swiping, so faces, logos and text must stay off the seams; continuous lines, horizons, gradients and stripes carry the illusion across (Krumzi).
- **Elements crossing the seam** (a cut-out, a photo, a word half on each slide) pull the viewer into the next swipe; standard in scrapbook carousels (vendor: [Ivory Mix](https://ivorymix.com/how-to-make-a-seamless-scrapbook-style-instagram-carousel-in-canva/)).
- **Length**: Krumzi recommends 3 slides as the balance; the cover must still work alone, cropped to 3:4 in the grid.
- **Swipe cue** on slide 1 (Krumzi).

## Trends

| Trend | Source | Fit for furniture |
|---|---|---|
| **Opt-Out Era**: clean layouts, serif, simple branding (searches +54%) | Canva Design Trends 2026, data from Canva searches + survey of 1,000 creators (press: [Ecommerce News, 2026-01-12](https://ecommercenews.com.au/story/canva-backs-imperfect-by-design-trend-in-2026-report), [Campaign India](https://www.campaignindia.in/article/2026-is-the-year-of-imperfect-by-design/506629)) | High |
| **Texture Check**: realistic materials and surfaces (+30%) | Canva 2026 | High (wood, fabric, stone) |
| **Notes App Chic**: scrapbook, candid behind-the-scenes | Canva 2026 | High (workshop) |
| **Zinegeist**: DIY zine, brutalist type posters (+77%) | Canva 2026 | Medium (zine yes, brutalism no) |
| DIY-style searches +90%, zine/Substack layouts +85%, lo-fi +527%; 80% of creators want creative control back from AI | Canva 2026 | Supports "handmade" looks |
| Bubbly and handwritten type, organic imperfect design, collage with doodles and stamps, local flavor | Vendor: [Adobe Express, 2025-12-12](https://www.adobe.com/express/learn/blog/design-trends-2026) | High for collage and handwriting accents |
| **Expressive minimalism** (clean layout + one bold element), anti-AI handmade, experimental type; Y2K chrome; controlled chaos | Vendor: [DesignCloud](https://designcloud.app/blog/graphic-design-trends) | High / high / medium; low; low |
| Neo-minimalism next to chaotic maximalism; "distorted" graphics +45% | Envato search data (press: [Campaign Brief](https://campaignbrief.com/?p=305818)) | Neo-minimalism high |
| Home decor 2026: **Neo Deco** (arches, chevrons, brass), dark moody palettes, stripes and sculptural pieces | Pinterest Predicts 2026 (press: [Axios, 2025-12-09](https://axios.com/2025/12/09/2026-pinterest-trend-report)) | High, as styling in scene prompts |
| Bento grids | Strong on the web, no evidence as an Instagram trend (vendor: [Feedspring](https://www.feedspring.com/blog/top-5-best-instagram-feed-designs)) | Medium |
| Tweet-style and notes-style text posts, much saved and shared | Anecdotal only ([forum](https://www.jeffbullas.com/thread/how-do-i-create-an-effective-tweet-style-image-post-for-instagram/)) | Medium |

Carousels still lead engagement: 0.50% in Q2 2026 vs 0.48% for Reels and 0.33% for images (data: [Socialinsider](https://www.socialinsider.io/blog/instagram-benchmarks/)).

## Slide anatomy

All vendor advice; there is no official safe-zone spec for carousels.

- **Cover hook**: 5 to 10 words ([ContentStudio](https://contentstudio.io/blog/instagram-carousel)) or under 40 characters ([TryMyPost](https://www.trymypost.com/blog/instagram-carousel-hook-design-principles-2026)); "1 of 7", a numbered list, or a before/after split. For before/after, show the **after** first ([Metricool, 2026-01-16](https://metricool.com/instagram-carousels/)).
- **Swipe cue and pagination**: an arrow or "Deslizá →" on slide 1 and a counter ("02/06") on the rest. The claim that an arrow lifts swipe-through 18% is unverified (TryMyPost).
- **Structure**: hook, why it matters, one point per slide, summary, then a specific CTA ("guardalo", not "seguinos"); 3 to 5 slides for product and before/after, 7 to 10 for educational ([Contentdrips, 2026-05-27](https://contentdrips.com/blog/2026/05/instagram-carousel-size-format/)).
- **Type on a 1080 px slide**: headline 60–90 px, section header 40–55 px, body 28–36 px (never under 28), labels 20–26 px; contrast at least 4.5:1; about 10 words per slide; one or two typefaces (Contentdrips). [PostNitro](https://postnitro.ai/blog/post/carousel-typography-guide-perfecting-font-sizes-and-spacing) goes larger: headlines 90–120 px, body about 40 px.
- **Margins**: 150 to 200 px from every edge (Contentdrips); leave room at the sides for the next slide's peek and the dots (socialk.it). Not verified, from the app: the feed draws a "1/N" counter at the top right and the tag icon at the bottom left, so keep both corners free.

Proposed renderer rules: body ≥ 32 px, headline ≥ 72 px, 96 px outer margin, cover content inside the central 1012 px, brand bar (logo, handle) at the bottom, our counter at the bottom right.

## Furniture and home decor brands

Brand feeds couldn't be read directly (Instagram serves a login page to automated requests), so this rests on reports and blogs and needs a manual pass.

- **Westwing**: a "shoppable magazine" with "Shop the Look" sets; 8.6 M Instagram followers ([2024 annual report](https://irpages2.eqs.com/download/companies/westwing/Annual%20Reports/Westwing_GB_2024_DE.pdf)). A Copenhagen Business School thesis on Westwing Italia found influencer images got the lowest engagement and recommended shoppable inspiration images ([CBS](https://research-api.cbs.dk/ws/portalfiles/portal/59807187/671251_MT122722.pdf), one study).
- **Carousel patterns** (vendor): one piece shown in several rooms, every colorway of a product in one carousel ([Influencer Marketing Hub](https://influencermarketinghub.com/how-to-use-instagram-carousels/)); a bundle sequence of sofa, rug, table, lamp ([Zeely](https://zeely.ai/blog/furniture-ads-examples/)); IKEA's student and small-space carousel ([MagicBrief](https://magicbrief.com/post/16-facebook-carousel-ad-examples-to-spark-your-inspiration)). Room scenes over product-on-white, and furniture as a high-save niche, are opinion ([Socialmon](https://www.socialmon.ai/blog/65-furniture-store-instagram-post-ideas-with-examples)).
- **Brand looks**: MUJI neutral and quiet, HAY color-forward and playful, IKEA colorful and pop (vendor: [Interior Insider](https://www.interiorinsider.com/article/muji-vs-ikea)).
- **Uruguay**, for a manual review: Estudio Claro, Diario, Fiorenza Emme, Zinc Design, Deco Rent ([Uruguay XXI furniture brochure](https://www.uruguayxxi.gub.uy/uploads/estatico/brochure%20mobiliario_V6.pdf)); and the reference stores in [furniture-decor-uruguay.md](../furniture-decor-uruguay.md).

## Template families for furniture

Shared chrome on every family: brand bar with logo and handle at the bottom, page counter at the bottom right, swipe arrow on the cover only, 96 px margin, CTA closing slide (save, message us, visit the store).

| # | Family | Look | Slides | Needs |
|---|---|---|---|---|
| 1 | **Ficha de producto** | Cut-out on a tinted solid background, soft shadow, thin dimension lines (W × D × H), serif name | Hero cut-out + name → detail callouts with arrows → dimensions → material swatches → CTA (4–6) | Cut-out, swatch colors, icons, logo |
| 2 | **Panorama del ambiente** (seamless) | One room across 3–5 slides, numbered dots with labels, a line crossing the seams | 3–5 slices of one canvas; cover works at 1012 px; item list; CTA | One wide image (generated or outpainted), logo |
| 3 | **Editorial / revista** | Masthead, issue number, oversized serif, column grid, pull quote | Magazine cover → story or tip slides with photo and caption → CTA (5–8) | 2–5 photos, logo |
| 4 | **Moodboard / scrapbook** | Paper texture, tape, polaroid frames, hand-drawn arrows, handwritten notes | Board cover → one look per slide (or seamless) → shop list | 3–6 photos or cut-outs, our tape and texture SVGs, CC0 doodles |
| 5 | **Shop the look** | Room hero with numbered dots, then one item per slide with a tag | Room cover → item 1…N → the set + CTA | Room photo, item cut-outs, logo |
| 6 | **Antes / después** | Split or stacked with "ANTES / DESPUÉS" pills; after first | After as cover → split → pieces used → CTA (3–5) | 2 photos |
| 7 | **Guía en números** | Huge numerals, line diagrams with dimension arrows ("3 medidas antes de comprar una mesa") | Hook → one number per slide → summary + CTA (5–8) | Cut-out or outline drawing, icons |
| 8 | **Colorways / variantes** | Same product in every color, swatch row, bento tiles | Grid of variants → one per slide → CTA | Cut-out per color |
| 9 | **Nota / tweet** | Notes-app or post-style card with big text, optional photo inset | Text hook → checklist → CTA | Logo, optional photo |

Families 3, 6, 7 (with a photo instead of a cut-out), 9 and 2 need only photos; 1, 5 and 8 need a cut-out pipeline ([recommendation.md](recommendation.md#cut-outs-needed-for-3-of-the-9-families)).

## Figures: icons and asset licenses

| Library | License | Use |
|---|---|---|
| [Lucide](https://lucide.dev/license) | ISC (Feather-derived icons MIT) | Yes; already in `frontend/` as `lucide-react` |
| [Phosphor](https://raw.githubusercontent.com/phosphor-icons/homepage/master/LICENSE), [Tabler](https://raw.githubusercontent.com/tabler/tabler-icons/main/LICENSE), [Iconoir](https://raw.githubusercontent.com/iconoir-icons/iconoir/main/LICENSE) | MIT | Yes |
| [Open Peeps](https://www.openpeeps.com/), [Humaaans](https://www.humaaans.com/), [Open Doodles](https://www.opendoodles.com/), [Khushmeen doodle icons](https://khushmeen.com/icons.html) | CC0 | Yes; Khushmeen's hand-drawn arrows and squiggles suit scrapbook |
| [unDraw](https://undraw.co/license) | Own license: no integrations, no automated access, no AI use | **No** |
| [Remix Icon](https://raw.githubusercontent.com/Remix-Design/RemixIcon/master/License) | Remix Icon License v1.0: no redistribution as a set, no logo use | Avoid |
| Fonts under [SIL OFL](https://openfontlicense.org/ofl-faq/) | Free to use in graphics | Yes (Google Fonts pairs) |
| [rembg](https://github.com/danielgatis/rembg) | MIT code, but the default `bria-rmbg` weights ([RMBG-2.0](https://huggingface.co/briaai/RMBG-2.0)) are CC BY-NC 4.0 | **Not the default model**; check other weights' licenses (BiRefNet's code is MIT, [weights not stated](https://github.com/ZhengPeng7/BiRefNet)) |

Tape strips, stickers, price tags, dimension lines and paper textures: draw our own SVGs, so there's nothing to license.
