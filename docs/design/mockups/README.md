# UI mockups

Second design pass of the MVP screens, drawn from [web-app.md](../web-app.md), [post-templates.md](../post-templates.md), [conversation-design.md](../../product/conversation-design.md) and [user-flows.md](../../product/user-flows.md). Scope and priorities: [ADR 0012](../../decisions/0012-catalog-content-dashboard-reels.md) (Catalog, content and Reels as the product direction) and [ADR 0016](../../decisions/0016-demo-scope-one-post.md) (what the MVP and the demo actually build).

**Live canvas:** <https://claude.ai/artifact/ERjbcMCaaW2d6u3P9cvZqD> (Claude Design canvas; ask the owner for the share link). The files here are a snapshot of its source taken on 2026-10-17 (second pass). Edit the canvas, not these files, and re-export when it changes.

## Files

[`canvas.json`](canvas.json) is the canvas index: one frame per artboard plus the row titles. Each `*.dc.html` file is one artboard. They load the canvas runtime (`./support.js`), which is not in the repo, so they don't render when opened straight from disk; open the live canvas to see them.

| Row | Artboards |
|---|---|
| 1 · WhatsApp | [Main](Main.dc.html) (welcome + magic link), [WA-02-Marca](WA-02-Marca.dc.html) (brand summary, then "¿En qué te puedo ayudar hoy?"), [WA-03-Plan](WA-03-Plan.dc.html) (plan on request), [WA-04-Post](WA-04-Post.dc.html), [WA-05-Cambio](WA-05-Cambio.dc.html), [WA-06-Publicar](WA-06-Publicar.dc.html) |
| 1b · After onboarding: a natural chat | [Chat-1-Fotos](Chat-1-Fotos.dc.html) (sends photos and asks for a post), [Chat-2-Ajuste](Chat-2-Ajuste.dc.html) (proposal, schedules by writing), [Chat-3-Ideas](Chat-3-Ideas.dc.html) (asks for ideas), [Chat-4-Charla](Chat-4-Charla.dc.html) (loose photo and questions), [Chat-5-Estilo-largo](Chat-5-Estilo-largo.dc.html) and [Chat-6-Estilo-corto](Chat-6-Estilo-corto.dc.html) (the bot matches how the Owner writes) |
| 2 · Onboarding wizard (`/o/[token]`) | [Wizard-1-Negocio](Wizard-1-Negocio.dc.html), [Wizard-2-Productos](Wizard-2-Productos.dc.html), [Wizard-3-Marca](Wizard-3-Marca.dc.html), [Wizard-4-Fotos](Wizard-4-Fotos.dc.html), [Wizard-5-Preferencias](Wizard-5-Preferencias.dc.html), [Wizard-6-Instagram](Wizard-6-Instagram.dc.html), [Wizard-6b-Feed](Wizard-6b-Feed.dc.html) (feed import), [Wizard-7-Listo](Wizard-7-Listo.dc.html), [Wizard-Link-vencido](Wizard-Link-vencido.dc.html), [WA-Sin-marca](WA-Sin-marca.dc.html) (no logo or colors: built in the chat) |
| 3 · Web | [Dashboard](Dashboard.dc.html), [Simulador](Simulador.dc.html) (`/dev/chat`), [Sistema](Sistema.dc.html) (tokens, type, controls, status badges) |
| 4 · Post templates (1080×1350; superseded by [ADR 0018](../../decisions/0018-ai-image-generation-service.md), post images are now AI-generated) | [Tpl-product-hero](Tpl-product-hero.dc.html), [Tpl-promo-band](Tpl-promo-band.dc.html), [Tpl-quote-card](Tpl-quote-card.dc.html), [Tpl-split-story](Tpl-split-story.dc.html) |

## Known gaps

- **Dashboard:** the artboard is the read-only Inicio page (Should). The editable Catálogo, Contenido and Promos tabs (Could, ADR 0012) are only wireframed in [web-app.md](../web-app.md), not drawn.
- **Out of scope in the mockups:** Chat-6 shows an Instagram story, which is Won't (F4.7). Wizard-6b feed import (F2.8) and WA-Sin-marca (F2.9) are Could; the wizard copy that mentions the feed only applies once F2.8 exists.
- **Placeholders:** the product and assistant names are still `[Nombre]` and `[dominio]`; photos are drawn shapes, not real images.
