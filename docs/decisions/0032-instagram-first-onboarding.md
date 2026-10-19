# 0032: Connect Instagram early in the wizard and let it answer for the Owner

- Date: 2026-10-18
- Status: proposed

## Context

[ADR 0028](0028-read-instagram-with-our-meta-app.md) added the Instagram connect as the wizard's last step (step 6) and kept everything it imports out of the wizard: imported photos didn't count toward the 3 to 15 photos and didn't show in the grid. A review of the wizard on 2026-10-18 found that this order makes the Owner do work Instagram already does:

- Step 1 asked for the Instagram handle, which the connect fills in anyway (`business.instagram_handle` is only text in two prompts).
- An Owner with a good feed still had to upload 3 photos before reaching the connect, and the import started last, so it was the most likely input to miss the 60 s `generate_brand` waits for it.
- The tone sliders defaulted to 3 and were always sent. Because the Brand Strategist's rule is "the form wins" over Instagram, an Owner who never touched a slider overrode their real voice.
- "Posts per week" is stored but nothing reads it: there is no scheduler (T30) and the post writer drops `brain.posting`.
- The three free-text brand words are only a hint ("include when they fit"), and typing three words is friction on a phone.

ADR 0028's caveats still hold: Instagram Login may not return captions, bio or website; serving Owners who aren't Instagram testers needs App Review; and publishing still goes to the demo account ([ADR 0024](0024-mvp-single-demo-instagram-account.md)).

## Decision

- **Connect Instagram as step 2**, right after the business basics, still optional ("No tengo, o lo hago después"). The import runs while the Owner fills in products. The OAuth callback and the connect endpoint don't change.
- **Imported photos show in the photos step and count toward the minimum.** The wizard state lists `source = 'instagram'` photos (`Asset.source`), the photos step shows them under "De @handle" with ✕ to drop one (the existing archive endpoint), and polls for up to 90 s while the import runs. `/complete` counts web and Instagram photos for the minimum of 3; the cap of 15 applies to the Owner's uploads only. This supersedes ADR 0028's consequence that imported photos stay out of the wizard.
- **Tone the Owner didn't choose is sent as null.** With Instagram connected, step 6 says the tone is learned from Instagram and only shows the sliders and the emoji question if the Owner taps "Prefiero elegirlo yo". `formality`, `humor` and `emoji_policy` are nullable; the Brand Strategist infers them from the captions when null, and uses 3, 3 and `few` without Instagram.
- **Drop the handle field and the posts-per-week question.** `posts_per_week` is nullable and the Brain defaults to 3.
- **Brand words become 1 to 3 chips**, suggested by the Business category (`frontend/lib/categories.ts`) plus a custom word. The same file gives category-specific examples and audiences, so a restaurant no longer sees furniture placeholders.
- `PUT /business` only overwrites `description`, `website` and `instagram_handle` when sent, so re-saving step 1 no longer erases what the import filled in. `location` is optional.

## Consequences

- An Owner with Instagram types less and reaches the brand step with real photos for its live post preview; one without Instagram follows the same manual path as before.
- The step 6b review grid is still not built: the Owner drops imported photos with ✕ in the existing grid, with no new endpoints.
- If the import takes longer than the 90 s the photos step waits, its photos still become Brand assets but the Owner may not see them in the wizard, and may need to upload 3 photos anyway.
- Connecting Instagram after completing the wizard still doesn't regenerate the Brand Brain ([open questions](../open-questions.md)).
- The tone the Agency uses for an Owner who skipped the sliders depends on how many captions Instagram Login returns; with none, it falls back to the neutral defaults.
