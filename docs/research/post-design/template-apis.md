# Hosted template-rendering APIs

Services where a designer builds a template in a visual editor and we fill it with data over an API. All sources read 2026-10-18. Every vendor bills per slide, so 1,000 credits is about 100 carousels of 10 slides, not 1,000.

Instagram limits that apply to all of them (JPEG only, at most 10 items, every item cropped to the first's ratio) are in [design-patterns.md](design-patterns.md#platform-limits).

## Shortlist

| Service | Templates | Carousel (multi-page) | API | Text fit | Price (cheapest fitting plan) | Python SDK |
|---|---|---|---|---|---|---|
| **Templated.io** | Own editor; Canva import by public link (beta since Oct 2025) | **Yes**: `pages` array with per-page data, one render per page (since 2025-06-30) | REST, sync by default (~2 s), optional async + webhook | `autofit` height/width with min/max size | Starter $29/month (annual) for 1,000 credits, 60 req/min, 15 templates; no overage | None official |
| **Orshot** | Own Studio; Figma (plugin) and Canva import | **Yes**: `page{N}@` keys per page, one URL per page, "Flow" overflow pages | REST; sync not stated | Fit, Truncate, Overflow, Flow | Free 100/month; Launch $39 for 1,500, overage $0.036 | `orshot` 0.2.0 |
| **Canva Connect (Autofill)** | Real Canva editor, brand templates with named fields | Export returns one URL per page | Two async jobs (autofill, export), OAuth per user; 60 req/min autofill, 20 req/min export; 500 exports/day per user | Canva's own | Opened to Pro, Teams and Enterprise on 2026-09-21/23 (was Enterprise-only); "usage limits will be introduced in the future"; requires MFA | None |
| **Placid** | Own editor | No (PDF only); one call per slide | REST, queued by default, `create_now` for immediate | "Fit" shrinks to box | 500–100,000 credits/month; prices not on the official page (third party: $19–249) | None (PHP, Laravel) |
| **Bannerbear** | Own editor | No; Template Sets give several images per payload | Async by default, sync host with 10 s timeout, batches of 100 | `auto_fit`, `resize_overflow` | $49/month for 1,000 credits | `bannerbear` 1.2.0 |
| **Polotno** | JS editor SDK; SVG import (Figma), PSD import | Not verified | Cloud Render, `Prefer: wait` for near-sync | `textOverflow` change-font-size, resize, ellipsis | $0.004 per render, plus an SDK subscription by quote | None |

Sources: Templated [render API](https://templated.io/docs/renders/create/), [multi-page](https://help.templated.io/en/article/multi-page-templates-1trfe67/), [Canva import](https://help.templated.io/en/article/import-from-canva-25ko2u/), [autofit](https://help.templated.io/en/article/text-autofit-feature-dljgdw/), [pricing](https://templated.io/pricing/). Orshot [multi-page](https://orshot.com/docs/image-generation/multi-page-images), [Figma](https://orshot.com/docs/integrations/figma), [text modes](https://orshot.com/help/text-sizing-modes.md), [pricing](https://orshot.com/pricing). Canva [Autofill guide](https://www.canva.dev/docs/connect/autofill-guide/), [changelog](https://www.canva.dev/docs/connect/changelog/), [autofill job](https://www.canva.dev/docs/connect/api-reference/autofills/create-design-autofill-job/), [export job](https://www.canva.dev/docs/connect/api-reference/exports/create-design-export-job/). Placid [images API](https://placid.app/docs/2.0/rest/images), [rate limit](https://placid.app/docs/2.0/rest/rate-limit), [pricing](https://placid.app/pricing), [third-party prices](https://trustradius.com/products/placid.app/pricing). Bannerbear [API](https://developers.bannerbear.com/), [pricing](https://www.bannerbear.com/pricing/). Polotno [Cloud Render API](https://polotno.com/docs/cloud-render-api), [price](https://polotno.com/cloud-render), [SDK pricing](https://polotno.com/sdk/pricing), [import](https://polotno.com/sdk/product/features/import).

Notes:

- **Templated.io** caps custom sizes at 100–5000 px; output jpg, png, webp, pdf, mp4. Its docs contradict themselves on the `async` default.
- **Canva**: images must first be uploaded as Canva assets; unknown field names are skipped silently; export links last 24 h. Whether Canva's content license lets us use its stock elements in posts for third parties is not verified.

## Skipped

- **Creatomate**: video-first, async, 3840 px cap, $54/month for 2,000 credits, no Python SDK, nothing carousel-specific ([API](https://creatomate.com/llms/api.md), [limits](https://creatomate.com/docs/api/reference/limits-and-concurrency)).
- **RenderForm**: $19/month for 1,000 credits, beta Figma importer; auto-fit, multi-page and rate limits not documented ([docs](https://renderform.io/docs/), [pricing](https://renderform.io/pricing/)).
- **APITemplate.io**: $29–35/month for 1,500 renders; v2 reference returned 403, auto-fit and multi-page not documented ([docs](https://docs.apitemplate.io/reference/api-reference.html), [pricing](https://apitemplate.io/pricing/)).
- **Figma as a renderer**: the REST API renders frames but can't change text ([file endpoints](https://developers.figma.com/docs/rest-api/file-endpoints/)); the Variables API workaround needs Enterprise, values are per file (concurrent renders collide), and image renders are 10–20 req/min ([variables](https://developers.figma.com/docs/rest-api/variables/), [rate limits](https://developers.figma.com/docs/rest-api/rate-limits/)). Figma works only as the design tool, imported into Orshot, RenderForm or Polotno.
- **Carousel SaaS** (PostNitro, Contentdrips, aiCarousels): they own the templates and target LinkedIn-style text carousels; PostNitro is $10/month for 250 credits, async ([docs](https://postnitro.ai/docs/llms.txt)); Contentdrips' pricing page contradicts itself ([API](https://developer.contentdrips.com/), [pricing](https://contentdrips.com/pricing)); aiCarousels has no public API ([site](https://www.aicarousels.com/)).

## Connected carousels

No vendor documents a design that spans slides. In a multi-page editor the designer duplicates each spanning element with an offset on the next page; or one wide canvas is rendered and sliced, which the size caps limit (Templated 5000 px, Creatomate 3840 px, Placid 8 credits above 4000 px) to 3–4 slides.

## Hosted vs our own renderer

- **Hosted, for**: designers iterate in a visual editor without deploys; text fitting and fonts solved; fastest to quality.
- **Hosted, against**: about $0.01–0.05 per slide; templates live in the vendor's editor; size caps break panoramas; async and webhook plumbing; output URLs expire (7–30 days), so we copy to Storage anyway.
- **Our own, for**: no per-render cost, any canvas width, layout logic in code (variable slide counts, numbering), templates in git.
- **Our own, against**: designs go through code, text fitting and fonts are ours to build, one more service to run.

Keeping the slide spec independent of the renderer lets us start hosted and move in-house later, or the reverse. Our pick is in [recommendation.md](recommendation.md).
