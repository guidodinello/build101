# 0027: The Owner's logo is stamped on post images in code

- Date: 2026-10-18
- Status: proposed
- Revised by: [0029](0029-designed-slides-ai-scene-code-layout.md) (on designed slides the template's brand mark places the logo)

## Context

The wizard lets the Owner upload a logo, but until now only its colors were used, for the Brand Brain palette. Owners ask for their logo on the post ("ponele el logo"), and the bot could neither do it nor know that it couldn't. Whether the real logo should appear on the image, and how, was an [open question](../open-questions.md#post-images-generated-by-ai-adr-0018), because the backend draws nothing since [ADR 0018](0018-ai-image-generation-service.md).

Two options:

- **Ask the image model to place the logo**, with the logo as a reference image. It can blend into the design, but image models distort logos and invent letters. That is the risk ADR 0018 and [ADR 0022](0022-carousels-in-mvp.md) ruled out with "do not draw, invent or alter any logo", and the Owner would have to check every logo by eye.
- **Stamp the logo file in code** on the finished image. It's the Owner's own file, pixel for pixel, only resized, but it sits on top of the design rather than inside it.

## Decision

- The logo is stamped in code with Pillow (`add_logo` in `backend/app/media/images.py`), only when the Owner asks: `create_post` takes `with_logo` (default false). The image prompts keep forbidding logos, so the model never draws one.
- The file is the latest logo from the wizard, in its **original upload** (PNG, WebP, JPEG or HEIC), not the agents' JPEG copy, which drops transparency.
- Placement: bottom-right corner, 4% of the width from the edges. Transparent margins are trimmed, then the logo is scaled to fit within 22% of the width and 9% of the height.
- Contrast: when a logo with transparency would blend into the photo behind it (mean luminance closer than 64 out of 255), it gets a rounded backing, white for dark logos and near-black for light ones. The backing, not the logo, then keeps the 4% margin. An opaque logo brings its own background and is pasted as it is.
- It goes on every image of the post, carousel slides included. For a design, the image model is asked to leave that corner free of text and of the product.
- If the Owner has no logo, `create_post` answers `no_logo`. The orchestrator learns whether a logo exists from `<brand_logo>` in the context block, so it never promises one it can't add.

## Consequences

- The logo is always exact and never distorted, and its corner and size are the same on every post. It doesn't adapt to each design the way a designer would place it.
- Each image gets one extra Pillow pass, a few milliseconds, in a thread.
- The design may still put something in the corner: the note in the prompt is a request, not a guarantee. The backing keeps the logo readable, and the Owner sees the post before approving it ([ADR 0007](0007-approve-every-post.md)).
- Not covered yet: uploading or replacing the logo from the chat, a remembered preference ("siempre con el logo") that survives a restart while history is in memory, choosing the corner, and the simple text logo of F2.9 (Could).
