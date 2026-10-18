# Image models for designed posts

What our image model can do for designed posts, and which alternatives do something it can't. All sources read 2026-10-18; quality claims are vendor marketing until tested on our own prompts. The provider choice is [ADR 0019](../../decisions/0019-image-provider-gemini.md); its comparison is [image-generation-providers.md](../image-generation-providers.md).

## Gemini Nano Banana 2.1

From the [image generation docs](https://ai.google.dev/gemini-api/docs/image-generation) and the [model page](https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1) ("Latest update: October 2026") unless noted.

- **Family**: `gemini-nano-banana-2.1` (our model), `gemini-3.1-flash-lite-image` (cheapest, 1K only, not for multi-reference), `gemini-3.1-flash-image` (Nano Banana 2, previous), `gemini-3-pro-image` (Nano Banana Pro, premium), `gemini-2.5-flash-image` (legacy).
- **Aspect ratios on 2.1**: 1:1, 1:4, 1:8, 2:3, 3:2, 3:4, 4:1, 4:3, 4:5, 5:4, 8:1, 9:16, 16:9, 21:9. Pro lacks 1:4, 4:1, 1:8 and 8:1. 2.1 "Fixed tiling artifacts on wide and panoramic aspect ratios (1:4, 4:1, 1:8, 8:1) at 2K and 4K."
- **Sizes**: 1K, 2K, 4K (default 1K). 4:1 at 4K = 8192 × 2048; 8:1 at 4K = 12288 × 1536.
- **References**: 2.1 and Nano Banana 2 take up to 10 object images and 4 character images, **with no style-reference slot**. Pro takes 6 objects, 5 characters and **up to 3 style references**. 14 images in total on every model. Our adapter labels the cover "Style reference:" (`backend/app/imagegen/gemini.py`), which 2.1 has no role for.
- **Text**: "Gemini works best if you first generate the text and then ask for an image with the text." The model "won't always follow the exact number of image outputs."
- **No transparency and no layers**: the docs don't mention transparent or layered output. No layout or bounding-box control; "advanced text rendering for infographics, menus, diagrams, and marketing assets" is a claim, not a control.
- **Multi-turn editing** via `previous_interaction_id` on the Interactions API, which Google now recommends for new projects; `generateContent`, which we use, "remains fully supported" ([Interactions](https://ai.google.dev/gemini-api/docs/interactions)).
- **Prices** ([pricing](https://ai.google.dev/gemini-api/docs/pricing)): 2.1 $0.0336 (1K), $0.0504 (2K), $0.113 (4K). Pro $0.134 (1K/2K), $0.24 (4K). Nano Banana 2 $0.101 (2K). The 4K token count is inconsistent on the page (3780 vs 2520 tokens).

## Prompting for design-like output

- **Gemini docs**, "Accurate text in images": "Be clear about the text, the font style (descriptively), and the overall design. Use Gemini 3 Pro Image for professional asset production." Also: be hyper-specific, say what the image is for, give complex scenes step by step, describe what you want rather than what you don't, and there is a "negative space" template for backgrounds that will carry text.
- **[Google Cloud guide, 2026-03-05](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana)**: put exact words in quotes and name the font; set hierarchy line by line (e.g. top line a brush script, middle "heavy, blocky Impact", bottom "thin Century Gothic"); say what each reference image is for ("use the attached X as the structure and Y as the texture"). Nothing on carousels, series or logos.
- **[blog.google, 2025-11-20](https://blog.google/products-and-platforms/products/gemini/prompting-tips-nano-banana-pro/)**: "clearly define the role of each" uploaded image; small text and spelling "may not work perfectly"; "character consistency across edits may vary".

## Seamless carousels from one wide image

- `4:1` is exactly 5 slides of 4:5 and `8:1` exactly 10 (arithmetic: a 4:5 slide is 0.8 wide per unit of height, so N slides are 0.8 N : 1). Other counts crop the nearest ratio: 2 slides (1.6) from 16:9, 3 (2.4) from 21:9, 4 (3.2) from 4:1, 6–9 from 8:1.
- At 4K, 4:1 gives five slices of about 1638 × 2048, which scale cleanly to 1080 × 1350; at 2K the slices are about 819 × 1024 and would need upscaling. One 4K image ($0.113) is cheaper than five 2K slides ($0.25).
- Slicing guidance (canvas of 1080 × N, keep faces, logos and words off seams, continuous lines across them): [Krumzi, 2026-09-03](https://www.krumzi.com/blog/seamless-instagram-carousel). No authoritative Nano Banana + slicing tutorial found.
- **Outpainting** to widen an existing photo into a panorama: [FLUX Outpainting](https://docs.bfl.ml/flux_tools/flux_outpainting.md) ($0.045–0.10), Recraft `/v1/images/outpaint` with `expand_left`/`expand_right` (V3 only), [Ideogram Reframe](https://developer.ideogram.ai/v2/api-reference/images/reframe/nano-banana-2.md).

## Alternatives that do something Gemini can't

| Model | What it adds | Price | Source |
|---|---|---|---|
| **Ideogram 4.5 / 3.0** | Structured JSON prompts, `background: transparent`, up to 10 style reference images and `color_palette` (3.0); **Layerize** (below) | Unverified (official page loads by JS); third party says $0.03 / $0.06 / $0.10 per image | [4.5](https://developer.ideogram.ai/v2/api-reference/images/generate/ideogram-4-5.md), [3.0](https://developer.ideogram.ai/v2/api-reference/images/generate/ideogram-3.md), [Wireflow](https://www.wireflow.ai/blog/ideogram-api-pricing) |
| **Recraft V4 / V4.1** | `_vector` models return **SVG**; V4 Styles makes a reusable `style_id` from 1–10 images; `controls.colors` with up to 10 brand colors; vectorize, remove-background, outpaint (V3) | Vector $0.08 (`recraftv4_1_vector`), pro vector $0.30, style $0.005, styled image $0.035 raster / $0.05 vector, vectorize $0.01, remove background $0.01 | [Recraft API](https://www.recraft.ai/docs/api-reference/agents.md), [models](https://www.recraft.ai/docs/api-reference/models/overview.md) |
| **FLUX 3 Image** (BFL) | Up to 10 references; **bounding-box layout prompts**: a box per text block with quoted text, case, color, type style, alignment | FLUX 3 not found; FLUX.2 [pro] from $0.03 | [layout prompting](https://docs.bfl.ml/guides/prompting_layout), [docs](https://docs.bfl.ai/llms.txt) |
| **Seedream 5.0 lite / 4.5 / 4.0** (ByteDance) | The only **native multi-image set**: `sequential_image_generation: auto`, `max_images` 1–15 (inputs + outputs ≤ 15); not on 5.0 pro or flash | Not checked | [BytePlus](https://docs.byteplus.com/en/docs/ModelArk/1541523) (read from search excerpt), [Wavespeed](https://wavespeed.ai/models/bytedance/seedream-v5.0-lite/sequential/llms.txt) |
| **Qwen-Image 2.0 / 3.0** | Aimed at slides, posters and infographics | Not checked | [2.0](https://qwen.ai/blog?id=qwen-image-2.0), [3.0](https://qwen.ai/blog?id=qwen-image-3.0) (pages need JS; from snippets) |
| **OpenAI gpt-image-2.5** | Transparent backgrounds, several references, multi-turn edits; up to 3840 px, ratios 1:3 to 3:1. Its own docs: "can still struggle with precise text placement", brand consistency "across multiple generations", "layout-sensitive compositions" | $30 per 1M image output tokens | [guide](https://developers.openai.com/api/docs/guides/image-generation.md), [pricing](https://developers.openai.com/api/docs/pricing.md) |

Recraft's `text_layout` (exact text boxes) works only on V3 and only with uppercase Latin text. Whether Recraft's SVG keeps text as `<text>` elements or outlines is not stated.

## Layered and transparent output

- **Ideogram Layerize** (`POST /v2/design/layerize/ideogram-3`): a flat image in, a **text-free base image** plus text blocks out, each with position and size, text, alignment, font name and alternatives, size, line height, hex color and a role (heading, subheading, body, caption); custom fonts can be uploaded ([docs](https://developer.ideogram.ai/v2/api-reference/images/layerize/ideogram-3.md)). The closest thing to "edit the model's text in code".
- **Qwen-Image-Layered** (Apache 2.0, 2025-12-19): splits an image into RGBA layers, exports PPTX/PSD; recommended at 640 px; no first-party API, [on Replicate](https://replicate.com/qwen/qwen-image-layered) ([repo](https://github.com/QwenLM/Qwen-Image-Layered)).
- **Transparent single elements** for compositing (cut-outs, stickers): Ideogram 4.5 and gpt-image-2.5 yes, Gemini no.

## Takeaways

- Gemini 2.1 is a good **photographer** for us (product fidelity, wide panoramas, cheap 4K) and a weak **designer** (no style slot, no layout control, no transparency, text in pixels).
- Keep Gemini for text-free scenes and panoramas; put text, figures and logo in templates ([recommendation.md](recommendation.md)).
- If we ever want model-rendered type for a stylised headline, Nano Banana Pro (style references) or FLUX 3 (bounding boxes), followed by Ideogram Layerize, is the path. Seedream's set mode is worth one A/B test.
