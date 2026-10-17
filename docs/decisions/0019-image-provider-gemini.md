# 0019: Image provider is Google Gemini, with OpenAI as fallback

- Date: 2026-10-17
- Status: proposed

## Context

[ADR 0018](0018-ai-image-generation-service.md) makes a third-party AI image service generate the post images, behind `ImageGenPort`, and leaves the provider open. The service must take the Owner's ~10 real product photos as reference images plus a prompt, return 4:5 images of at least 1080×1350, be callable from the Python backend, and not train on the Owner's photos.

Options are compared in [research/image-generation-providers.md](../research/image-generation-providers.md) (all facts below come from it, read 2026-10-17 from vendor docs; nothing was tested hands-on). In short:

- **Google Gemini `gemini-nano-banana-2.1`**: up to 10 object reference images "with high-fidelity" (14 in total); the docs list 4:5 natively, at 2K = 1856×2304 (1K = 928×1152 is too small); official `google-genai` Python SDK, synchronous, image returned as base64; **$0.0504** per 2K output image, plus input tokens ($1.50/1M) and thinking tokens ($7.50/1M, thinking can be set to `minimal`); no API free tier for image models, so a Cloud billing account must be linked (Tier 1: $10 per 10 minutes spend limit, $250 billing cap); paid-tier prompts and images are not used for training, while unpaid use (AI Studio, free quota) is. The model "won't always follow the exact number of image outputs", so the docs' advice implies one image per call.
- **OpenAI `gpt-image-2.5-sunburst`** via `POST /v1/images/edits`: up to 16 reference images; custom size `1088x1360` (exactly 4:5); official `openai` SDK; no training on API data unless opted in, 30-day abuse logs; per-image price **not verifiable** from the docs (token-priced, the calculator does not cover 2.5); "complex prompts may take up to 2 minutes"; may require API Organization Verification; 20 images per minute on a new account.
- **FLUX 3 Image (Black Forest Labs)**: fits technically, but its default API terms let BFL train on inputs and outputs.
- **fal.ai / Replicate**: one key for many models, but a second processor of the Owner's photos and a markup over going direct.

Product fidelity claims are vendor marketing for every option; there is no independent benchmark of multi-reference product identity.

## Decision

- **Primary: Google Gemini `gemini-nano-banana-2.1`** through the Gemini API and the official Python SDK (`google-genai`), with a linked billing account (paid tier) from the first call. Request 4:5 at 2K, one image per call, and run the variations in parallel; the backend resizes and crops the result to 1080×1350 ([ADR 0018](0018-ai-image-generation-service.md)).
- **Fallback: OpenAI `gpt-image-2.5-sunburst`** through `POST /v1/images/edits` with size `1088x1360`, downscaled to 1080×1350. Different vendor, so an outage or a moderation block on one does not stop the demo.
- Both are adapters behind `ImageGenPort`; switching is configuration, not code.
- Points the docs leave open are confirmed on the first real call, before building on them: that `gemini-nano-banana-2.1` accepts `aspect_ratio: "4:5"` with `image_size: "2K"` and returns 1856×2304, the latency per image, and the images-per-minute limit for a new Tier 1 project (not on the public page).

## Consequences

- Cost per variation is measured, not assumed: log the response `usage` (input images, prompt, thinking, output) with every call and compute dollars per variation. For OpenAI this is the only way to know the price.
- Fidelity is tested first, with the demo business's real photos: the same photos and brief through both providers, checking shape, color, material and proportions of the real product, and that "no text" prompting keeps prices, logos and slogans out. Results go into the research doc.
- Real Owner photos are never sent to Gemini without billing enabled, because unpaid use is used for training.
- OpenAI's Organization Verification is done only if the fallback is actually needed; until then only `GEMINI_API_KEY` is required.
- Every Gemini output carries an invisible SynthID watermark.
- New secrets: `GEMINI_API_KEY`, and `OPENAI_API_KEY` for the fallback.
