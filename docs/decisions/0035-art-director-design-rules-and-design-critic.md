# 0035: The Art Director designs with rules, layout knobs and brand fonts, and a Design Critic reviews every rendered carousel

- Date: 2026-10-25
- Status: proposed
- Amends: [0029](0029-designed-slides-ai-scene-code-layout.md)

## Context

[ADR 0029](0029-designed-slides-ai-scene-code-layout.md) moved text and layout from the image model to code templates, and text became exact. The designs still read as generic: three fixed templates, the same fonts for every brand, small and quiet type, and body text that sat over busy parts of a photo. The Art Director's only design decision was one of three family names, its prompt had no design knowledge, and nobody looked at a rendered slide before the Owner did.

People get professional design work out of LLMs by combining four things: design rules in the prompt, code as the medium, a step that looks at the rendered result and fixes it, and good references. We had only the second. Before and after renders, and how to run the comparison: [research/post-design/designer-agent.md](../research/post-design/designer-agent.md).

Alternatives considered:

- **Free-form layouts:** the model writes the layout, as JSX or HTML, for each slide. It gives the most variety, but quality varies from call to call, and running model-written code in the renderer is code injection. A constrained JSON layout language is the safe form of it. We do it only if the design eval shows that the families and knobs below are not enough.
- **Better templates only, no review at runtime:** cheaper and faster, but a template can't see that this photo's product sits under this headline.
- **A hosted template API** ([template-apis.md](../research/post-design/template-apis.md)) changes where templates are drawn, not how good they are.

## Decision

- **Six families with layouts per role:** `editorial`, `numbers`, `panorama`, plus the new `minimal`, `notes` (text cards and checklists over a blurred photo) and `scrapbook` (instant photos, tape, handwritten notes). Each slide carries knobs the Art Director sets: `layout` (from its family's list), `emphasis` (`standard` or `statement`), `focus` (where the product sits, for the crop) and `surface` (`paper`, `brand`, `dark`), plus `items` for checklists. Scenes are framed for the layout the renderer will draw. The lists live in `backend/app/carousel/schemas.py` and `frontend/lib/post-render/spec.ts`.
- **Brand typography:** the Brand Brain gets `visual_identity.font_pair`, one of six curated OFL pairs, chosen by the Brand Strategist. Brand Brains stored before this ADR read as `serif-classic` until they are revised.
- **The renderer checks its own work:** headlines and bodies are fitted with Takumi's `measure()`, so text never overflows. The scene's pixels decide the text color and the strength of the shade under it, aiming at 4.5:1 contrast and a stronger shade over busy patches. Each render returns an `x-render-report` header with the fitted sizes, any clamped slot and the contrast reached.
- **Design rules in the Art Director's prompt** (`backend/app/posts/prompts/design.md`): hierarchy, word limits, rhythm across slides, photo direction, and how to pick the family by content and by brand.
- **A Design Critic** (`backend/app/posts/critic.py`) makes one structured vision call after rendering. It sees the slides at half size and the render reports, and per slide answers `ok`, a knob fix, or a new scene (at most two per carousel, never for a panorama). The changed slides are rendered once more, with no second review. A failed review sends the post as rendered. It runs only with `RENDERER=takumi` and can be switched off with `DESIGN_CRITIC=false`.
- **Models are configurable per role:** `ART_DIRECTOR_MODEL` and `DESIGN_CRITIC_MODEL` take a Gemini model or a Claude model (`ClaudeStructured` on the official `anthropic` SDK, structured output only). The default stays `GEMINI_CHAT_MODEL` ([ADR 0023](0023-gemini-text-llm.md)). The choice is made with `python -m app.posts.design_eval`, which runs fixed briefs end to end and builds a blind A/B page.

## Consequences

- A designed post costs one more vision call, up to two more images and a second render. It also takes longer: the review itself plus up to a minute when a scene is regenerated. Posts already run in the background behind a holding message.
- **Deploy the frontend first.** The renderer before this ADR answers 400 to the new families, so a newer backend in front of it fails every post that picks `minimal`, `notes` or `scrapbook`. The new fields are optional, so the new renderer works with the old backend.
- The family and layout lists are duplicated in Python and TypeScript, each pointing at the other. `resolved_layout` in `app/carousel/prompts.py` mirrors the frontend's layout choice to frame the scenes, so a new layout must be added in both.
- The renderer bundles about 350 KB more of fonts. A pair is a code change: font files, `TYPEFACES`, the `FontPair` literal and the Brand Strategist's prompt.
- `anthropic` is a new backend dependency, used only when a role is set to a Claude model, which also needs `ANTHROPIC_API_KEY`. The orchestrator stays on Gemini: its history is stored in Gemini's step format.
- Free-form layouts stay open and gated on the design eval ([open questions](../open-questions.md)).
