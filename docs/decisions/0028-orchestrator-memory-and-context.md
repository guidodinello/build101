# 0028: The orchestrator's memory and context

- Date: 2026-10-18
- Status: proposed

## Context

Owners found the WhatsApp assistant forgetful and slow to understand them. The investigation in [research/orchestrator-intelligence.md](../research/orchestrator-intelligence.md) traced it to the context, not the model: the orchestrator never saw the Brand Brain, its history was 40 in-memory steps cut without a summary and lost on every deploy, a keyword check refused "sí" and "dale" after "¿Lo subo?", and a change to a sent post rebuilt it from a one-line brief. [agents.md § Orchestrator](../architecture/agents.md#orchestrator) had already planned a brand block, a context block with `<now>` and history in the database; none of it was built.

## Decision

- **History in Postgres.** The orchestrator's steps, thought steps included, are stored one per row in `conversation_steps` and resent unchanged, keyed by Business. A deploy or crash no longer erases the conversation. Without a database (local runs) the history stays in memory.
- **A token budget with a summary, not a step cap.** Past about 40,000 estimated tokens, the oldest whole turns are folded into `businesses.conversation_summary` by one structured call (`conversation_summarizer`, thinking `low`) and deleted, keeping about 20,000 tokens word for word. The summary rides in the system prompt. If summarizing fails, the history waits for the next turn, and only past three times the budget are old turns dropped without a summary.
- **What the model knows rides in the system prompt**: the Business row and its current offer, the latest Brand Brain and the summary the Owner was shown, the Catalog, the Owner's notes, the week's trend notes and the conversation summary. It changes only when one of them changes, so the prefix still caches. `<now>` (local date and time) rides on the Owner's message with the photo blocks.
- **Owner notes.** `remember` and `forget` tools keep standing preferences and facts ("no poner precios", "abrimos sábados") in `owner_notes`, archived when forgotten. The post writer reads them too, and they win over the Brand Brain when they conflict. A change to the brand itself goes through `update_brand` (the Brand Strategist's revise mode, with a new summary to confirm), which also replaces the code that took any message after "Corregir algo" as the correction.
- **Edit, don't rebuild.** `revise_post(post_id, change, part)` remakes a sent post from its previous version (brief, caption, headlines, `style_prompt`) with "change only what was asked". `part = caption` keeps the images and generates nothing. `create_post(replaces=...)` also passes the previous version, for other photos or the other style.
- **Approval answers the question.** A reply made only of yes words ("sí", "dale", "ok", "👍") approves the post the assistant's last message asked to publish ("¿Lo subo?"), detected in code from that message. It still applies [ADR 0007](0007-approve-every-post.md): approval is decided in code and is explicit. Photos block an approval only when they arrived after the pending posts.
- **Chat photos are described and kept.** Each photo the Owner sends goes through the Asset Analyst in the background; its description shows in `<recent_photos>`, and with the database it is stored as a Brand asset (`source = 'whatsapp'`), so it is offered as a `b` photo after the 30 minutes of `<recent_photos>`.
- **More reasoning where it matters**: thinking `medium` for the Owner's turns (and photos without text), `low` for event turns.
- **Evals.** `tests/test_conversation_live.py` runs multi-turn scenarios on the real model (`-m live`): business knowledge, a note saved, "dale" publishes, a caption edit generates nothing, a fact survives compaction.

## Consequences

- One more structured call per chat photo, and one per compaction. The Owner's turns take somewhat longer at `medium`; the 20-second holding message covers the slow ones.
- Posts and their images still live in memory (T17, T19): after a restart the conversation remembers a post that can no longer be approved. The model says so through `list_posts` and the `unknown_post` error.
- The onboarding gate's own messages (welcome, link) stay out of the history: the Business block already carries what they collected.
- A chat photo appears once, as `f` while recent and as `b` after; the context block hides the `b` copy of a recent `f` photo.
- The planned `get_brand_summary` and `suggest_ideas` tools are not needed: the brand is in the prompt, and the orchestrator writes ideas from the pillars and trend notes itself.
