# 0012: Catalog and content dashboard, with Reels from the Owner's videos

- Date: 2026-10-17
- Status: proposed
- Priorities revised by: [0016](0016-demo-scope-one-post.md)

## Context

The agents can only be as good as the material the Owner gives them. The MVP capped onboarding at 5 products and 15 photos, kept products inside the Brand Brain, made the dashboard read-only (F6.3 *Should*) and ruled out Reels (F4.7 *Won't*). The team wants Owners to upload as much catalog and content as they can, including loose videos, because that material is what makes Posts and Reels possible. Facts behind the limits below: [research/media-uploads.md](../research/media-uploads.md).

Alternatives considered: keep uploads in the wizard only (too little material, no way to add more later); edit videos ourselves (cuts, overlays, music), which is too much for 24 hours; keep Reels for after the hackathon (rejected: video is what Owners already have on their phones).

## Decision

- The dashboard (`/b/[token]`) becomes a **Must** and is editable. The Owner manages the **Catalog** (Products) and their **Brand assets** (photos and videos) there. WhatsApp stays the main door; the web is the side door for bulk uploads.
- **Products** are their own entity, unlimited, linked many-to-many to Brand assets. The Brand Brain keeps only a summary of the main ones.
- Uploads go **browser → Supabase Storage** through signed upload URLs (resumable above 6 MB). We use the Supabase **Pro** plan from the hackathon, because the Free plan caps files at 50 MB.
- The Asset Analyst reads videos through **keyframes extracted with ffmpeg** in the backend (Claude takes no video or audio). It also saves the best frames as derived photos. No transcription in the MVP.
- A **Reel** is one of the Owner's own videos, unedited, published with a caption written by the Copywriter and a chosen cover frame. It goes through the same Approval as any Post. We do no video editing in the MVP.
- **Offers** (packs and promos) are defined by the Owner, replacing `current_offers` in the Brand Brain. The Agency suggesting Offers is post-MVP.

## Consequences

- More and better material for every agent; the Content Strategist can plan Reels when there are suitable videos.
- A Post now has a format (image or Reel), and the publisher, the WhatsApp preview and the revision loop handle both.
- Anyone with the dashboard link can edit, until there are user accounts (F7.4). Links expire after 7 days, and removing material only archives it.
- Cost: Supabase Pro (US$25/month) from day one, replacing the free tier assumed in [ADR 0003](0003-database-supabase-sqlalchemy.md); the backend image needs ffmpeg.
- The 24-hour plan gets heavier, so other Should items move down.
