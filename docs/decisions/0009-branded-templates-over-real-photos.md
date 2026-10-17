# 0009: Branded HTML templates over the owner's real photos

- Date: 2026-10-17
- Status: superseded
- Superseded by: [0018](0018-ai-image-generation-service.md)

## Context

We only have an Anthropic key (no image-generation key). Furniture is a product category where real photos sell better than generated images, and AI-generated text inside images is often broken.

## Decision

The Art Director agent **chooses** a template, a real photo uploaded by the owner, brand colors and short texts (a render spec). A deterministic renderer (Jinja2 HTML + Playwright) produces the 1080×1350 image. AI image generation stays behind an optional `ImageGenPort`.

## Consequences

- Consistent, on-brand, legible images; no hallucinated products.
- Visual variety is limited by the number of templates (4 in the MVP).
- Requires the owner to upload decent photos; onboarding asks for at least 3.
