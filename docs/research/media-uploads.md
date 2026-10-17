# Media uploads: storage, vision, video publishing

Facts behind the Catalog and Brand asset upload work: where large photos and videos can be stored, what the agents can read, and what can be published to Instagram. All sources read 2026-10-17.

## Storage (Supabase)

- Max file size per file: Free **50 MB**, Pro **500 GB**. The global limit caps every bucket; a bucket limit can only be lower. [Supabase file limits](https://supabase.com/docs/guides/storage/uploads/file-limits)
- Free plan: **1 GB** storage, 5 GB egress, **no image transformations**. Pro: 100 GB included (then $0.0213/GB), 250 GB egress. [Supabase pricing](https://supabase.com/pricing)
- Standard uploads are meant for files up to **6 MB**; above that use resumable (TUS) uploads (6 MB chunks, upload URL valid up to 24 h, one client per URL). [Standard uploads](https://supabase.com/docs/guides/storage/uploads/standard-uploads), [Resumable uploads](https://supabase.com/docs/guides/storage/uploads/resumable-uploads)
- The backend can issue a **signed upload URL** (`createSignedUploadUrl`, valid 2 h) that the browser uses without further auth; TUS accepts the signed token in `x-signature`. [createSignedUploadUrl](https://supabase.com/docs/reference/javascript/storage-from-createsigneduploadurl)
- Image transformations (Pro only): 1–2500 px output, source ≤ 25 MB / 50 MP, HEIC as input only. [Image transformations](https://supabase.com/docs/guides/storage/serving/image-transformations)
- Not confirmed: which RLS policy signed upload URLs require.

## Web uploads (Vercel)

- Vercel Function request bodies are capped at **4.5 MB** (`413 FUNCTION_PAYLOAD_TOO_LARGE`); Vercel recommends uploading straight to storage. [Vercel limitations](https://vercel.com/docs/functions/limitations), [Bypass body size limit](https://vercel.com/kb/guide/how-to-bypass-vercel-body-size-limit-serverless-functions)
- The browser calls the FastAPI backend directly ([architecture/api.md](../architecture/api.md)), so this only bites if uploads went through Next.js. Streaming 300 MB videos through our single backend instance ([ADR 0005](../decisions/0005-single-instance-in-process-jobs.md)) is a bad idea anyway, so photos and videos go **browser → Supabase** with signed URLs; the backend only issues URLs and records metadata.

## What Claude can read

- The Messages API takes text, images and documents; **no video or audio** content blocks. [Messages API](https://platform.claude.com/docs/en/api/messages/create), [Files API](https://platform.claude.com/docs/en/build-with-claude/files)
- Images: JPEG, PNG, GIF (first frame), WebP; up to 100 per request on 200k-context models (600 on others); 8000×8000 px and 10 MB each; 32 MB per request. Above 20 images per request keep each side ≤ 2000 px. [Vision](https://platform.claude.com/docs/en/build-with-claude/vision)
- Video understanding: no official Anthropic guide. The common community pattern is extracting keyframes with ffmpeg and sending them as images, plus a separate transcript ([example](https://github.com/jordanrendric/claude-video-vision)). Frame extraction has to run in our backend: the code execution tool has no ffmpeg and no internet. [Code execution tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool)
- Audio: Anthropic has no speech-to-text endpoint (none found). Transcription needs `faster-whisper` in the backend container (already the optional plan in [architecture/integrations.md](../architecture/integrations.md)) or a second provider.

## Publishing video and carousels (Zernio, Instagram)

- Zernio publishes a single video as a **Reel**; carousels take up to **10** items and can mix images and video, cropped to the first item's ratio. Reel limits per Zernio: MP4/MOV, H.264, 3–90 s, 300 MB, 9:16. Cover via `thumbOffset` or a cover image. [Zernio Instagram](https://docs.zernio.com/platforms/instagram)
- Zernio takes media by public HTTPS URL or through its presigned upload (`POST /v1/media/presign`, 5 GB cap, files kept 7 days). [Zernio media uploads](https://docs.zernio.com/guides/media-uploads)
- Instagram Reels: MOV/MP4, H.264 or HEVC, AAC audio, 23–60 fps, 3 s to **15 min**, 300 MB; container → poll status → `media_publish`. Images: JPEG only, ≤ 8 MB. Carousels: up to 10 items, Reels can't be carousel items. [IG content publishing](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing), [IG media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media)

## Conflicts to test

- Reel length: Zernio says 90 s, Meta says 15 min.
- Zernio's quick reference says "one video per post", while its carousel section allows video items.
- Meta's publishing limit appears as both 100 and 50 posts per 24 h; check `GET /<IG_ID>/content_publishing_limit`.
- Whether Zernio converts PNG to JPEG (Meta accepts JPEG only).
