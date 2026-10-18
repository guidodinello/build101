# Rendering templates in code

Options for turning a template plus JSON data into a 1080 × 1350 JPEG without running Chromium in the backend, which [ADR 0018](../../decisions/0018-ai-image-generation-service.md) removed to fit Railway's 1 GB container ([ADR 0017](../../decisions/0017-backend-host-railway.md)). All sources read 2026-10-18; no render times or memory were measured by us.

## Takumi

- **What**: one Rust engine that takes JSX, HTML strings or node trees and outputs PNG, JPEG, WebP or SVG directly, plus animated GIF/APNG/WebP and PDF ([comparison to Satori](https://takumi.kane.tw/docs/comparison-to-satori)).
- **CSS**: flexbox, grid, block, inline, float; stylesheets, `::before`/`::after`, `calc()`, `@media`, `z-index`, `backdrop-filter`, blend modes, RTL, Tailwind via `tw` (same page). Text: `line-clamp`, `text-wrap: balance`, stroke, shadow, variable fonts ([typography](https://takumi.kane.tw/docs/typography-and-fonts)). Still a subset of browser CSS ([repo](https://github.com/kane50613/takumi)).
- **Fonts**: WOFF2 supported, `googleFonts()` helper, a Latin-only Geist fallback, no system fonts.
- **Next.js**: `takumi-js/response` exposes an `ImageResponse` with the same API as `next/og`; add `serverExternalPackages: ["@takumi-rs/core"]` ([Next.js integration](https://takumi.kane.tw/docs/integration/nextjs)). Divs default to `block`, so Satori-style templates need explicit `display: flex`.
- **Runtimes**: native Node/Bun binding (`@takumi-rs/core`), WASM for edge and browser, a Rust crate.
- **Performance**: in the project's 65-template benchmark, RSS 189–235 MB by default, 114–130 MB with a glibc malloc tunable; canvas limit 64 megapixels (a 10-slide strip of 10800 × 1350 is 14.6 MP); renders run off the event loop; no ms-per-render figure published ([performance](https://takumi.kane.tw/docs/performance-and-optimization)). About 8.6 MB installed.
- **Maturity**: about 3.1k stars, in the Vercel OSS Program, used by TanStack, Nuxt OG Image, Luma and Dcard; MIT or Apache-2.0 ([repo](https://github.com/kane50613/takumi)). Current `takumi-js` 2.16.3.
- **Python**: only an unofficial `takumi-py` 0.3.0 (third party, GPL-3.0-or-later, "testing stage, not a stable production dependency", 9 stars) ([repo](https://github.com/BalconyJH/takumi-py), [PyPI](https://pypi.org/pypi/takumi-py/json)). Not for us.

## `next/og` and Satori

- **`next/og` / `ImageResponse`**: JSX with inline styles → Satori (SVG) → resvg (PNG). The docs say "Only flexbox and a subset of CSS properties… `display: grid` will not work"; absolute positioning and text wrapping work ([Next.js docs](https://nextjs.org/docs/app/api-reference/functions/image-response)). Fonts TTF, OTF, WOFF (no WOFF2); a documented 500 KB limit for JSX + CSS + fonts + images ([Vercel OG](https://vercel.com/docs/og-image-generation)), which seems to date from the Edge runtime.
- **The version Next ships is old**: Next 16.4.2 bundles `@vercel/og` 1.0.1 with satori 0.29.0 (flex-only); the latest `@vercel/og` 1.0.3 pins satori 0.33.5 ([npm](https://registry.npmjs.org/@vercel/og)). MPL-2.0.
- **Standalone Satori 0.62.0** (2026-10-16) caught up fast: Taffy layout with grid, block and float, `z-index`, 3D transforms, filters, masks, `clip-path`, blend modes, `<style>` with selectors, WOFF2 ([repo](https://github.com/vercel/satori)). About 30 releases between 2026-10-02 and 10-16 ([releases](https://github.com/vercel/satori/releases)), so it's moving under our feet. Outputs SVG only; needs resvg or Sharp for a raster.
- **Edge runtime** is no longer supported from Next.js 16.3; Vercel recommends Node.js ([Vercel](https://vercel.com/docs/functions/runtimes/edge)).

## Vercel function limits

From [Vercel limits](https://vercel.com/docs/functions/limitations): 250 MB uncompressed bundle; 2 GB memory on Hobby, up to 4 GB on Pro; 300 s max on Hobby, 800 s on Pro; **4.5 MB max response body**. A 1080 × 1350 JPEG is far under that; a 10-slide strip in one response may not be, so render one slide per call (the wide canvas shifted by `−i × 1080 px`) or upload to Storage.

## Python, without a browser

| Library | What it gives | Catch | Source |
|---|---|---|---|
| **resvg-py** 0.5.0 (MIT) | SVG → PNG via Rust resvg; font files and dirs; pixel-identical across platforms, ~1,600 regression tests | SVG has no automatic text wrapping: we'd measure and break lines ourselves (not verified in its docs); two PyPI packages share the name (`resvg-py`, `resvg`) | [docs](https://resvg-py.readthedocs.io/en/latest/fonts.html), [resvg](https://github.com/linebender/resvg), [PyPI](https://pypi.org/pypi/resvg/json) |
| **Pillow** 13.0.0 | Already in the backend; `multiline_text`, justify, anchors, stroke, rounded rectangles | No wrapping, no SVG, OpenType features need libraqm; layout by hand | [ImageDraw](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html) |
| **skia-python** 144 (BSD-3) | Skia canvas, Linux wheels | Couldn't confirm paragraph layout (SkParagraph) or SVG support | [repo](https://github.com/kyamagu/skia-python) |
| **CairoSVG** 2.9.1 (LGPL-3.0) | SVG → PNG | Its docs call text support "poor": no kerning, letter spacing or `@font-face` | [docs](https://cairosvg.org/documentation/) |
| **WeasyPrint** 70 | HTML/CSS layout | PDF only since v53 | [changelog](https://doc.courtbouillon.org/weasyprint/stable/changelog.html) |
| **html2image** | HTML → image | Wraps a headless Chrome | [repo](https://github.com/vgalin/html2image) |

Young Pillow-based carousel libraries exist (`kalve` 0.1.1, `bearcarousel` 0.2.0 alpha) ([kalve](https://pypi.org/project/kalve/), [bearcarousel](https://github.com/johnnyang0612/bearcarousel)), too early to depend on. [open-carrusel](https://github.com/Hainrixz/open-carrusel) (MIT, Next.js + Puppeteer, Claude-driven) is worth reading for template ideas.

## Headless Chromium as a separate service

- Full CSS fidelity, heaviest runtime: Chromium needs "at least 512Mi at idle — use 1Gi for production" ([OpenFaaS](https://docs.openfaas.com/languages/python/examples/playwright/)); Docker's default 64 MB `/dev/shm` is too small ([Browserless](https://www.browserless.io/blog/run-playwright-in-docker)).
- Hosted: Browserless, annual billing, one unit = 30 s of browser time: free 1k units; $25/month 20k units, 10 concurrent; $140/month 180k ([pricing](https://www.browserless.io/pricing)).
- Polotno's server renderer and Fabric.js server-side also run on Chromium or node-canvas ([polotno-node](https://registry.npmjs.org/polotno-node), [Fabric.js](https://registry.npmjs.org/fabric/7.4.0)).

## Takeaway

**Takumi in a Node route handler of the Next.js app on Vercel** is the best fit: grid and layering for real layouts, JPEG out, no Chromium, permissive license, templates as React components next to the frontend, and a canvas big enough for a 10-slide strip. The cost is a second service to call and a CSS subset that needs a visual check per template. If rendering must stay in Python, Jinja → SVG → resvg-py is the robust option, with our own line breaking. Avoid `next/og` as bundled (flex-only, old Satori) and Chromium on the Railway container.
