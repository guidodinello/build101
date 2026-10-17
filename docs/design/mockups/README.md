# UI mockups

First design pass of the MVP screens, drawn from [web-app.md](../web-app.md), [post-templates.md](../post-templates.md), [conversation-design.md](../../product/conversation-design.md) and [user-flows.md](../../product/user-flows.md).

**Live canvas:** <https://claude.ai/artifact/ERjbcMCaaW2d6u3P9cvZqD> (Claude Design canvas; ask the owner for the share link). The files here are a snapshot of its source taken on 2026-10-17. Edit the canvas, not these files, and re-export when it changes.

## Files

[`canvas.json`](canvas.json) is the canvas index: one frame per artboard plus the row titles. Each `*.dc.html` file is one artboard. They load the canvas runtime (`./support.js`), which is not in the repo, so they don't render when opened straight from disk; open the live canvas to see them.

| Row | Artboards |
|---|---|
| 1 · WhatsApp | [Main](Main.dc.html) (welcome + magic link), [WA-02-Marca](WA-02-Marca.dc.html), [WA-03-Plan](WA-03-Plan.dc.html), [WA-04-Post](WA-04-Post.dc.html), [WA-05-Cambio](WA-05-Cambio.dc.html), [WA-06-Publicar](WA-06-Publicar.dc.html) |
| 2 · Onboarding wizard (`/o/[token]`) | [Wizard-1-Negocio](Wizard-1-Negocio.dc.html), [Wizard-2-Productos](Wizard-2-Productos.dc.html), [Wizard-3-Marca](Wizard-3-Marca.dc.html), [Wizard-4-Fotos](Wizard-4-Fotos.dc.html), [Wizard-5-Preferencias](Wizard-5-Preferencias.dc.html), [Wizard-6-Instagram](Wizard-6-Instagram.dc.html), [Wizard-7-Listo](Wizard-7-Listo.dc.html), [Wizard-Link-vencido](Wizard-Link-vencido.dc.html) |
| 3 · Web | [Dashboard](Dashboard.dc.html), [Simulador](Simulador.dc.html) (`/dev/chat`), [Sistema](Sistema.dc.html) (tokens, controls, status badges) |
| 4 · Post templates (1080×1350) | [Tpl-product-hero](Tpl-product-hero.dc.html), [Tpl-promo-band](Tpl-promo-band.dc.html), [Tpl-quote-card](Tpl-quote-card.dc.html), [Tpl-split-story](Tpl-split-story.dc.html) |

## Known gaps

- **Behind ADR 0012** ([PR #7](https://github.com/guidodinello/build101/pull/7), catalog and content dashboard with Reels): the dashboard is still the read-only version, wizard step 2 still has the old product cap, and step 4 has photos only. Missing: the dashboard's Catálogo, Contenido and Promos tabs, video uploads, and a Reel preview in WhatsApp.
- **Fonts differ from [web-app.md](../web-app.md):** the mockups use Bricolage Grotesque (headings) and Figtree (body) instead of Inter. Pending team agreement.
- **Placeholders:** the product and assistant names are still `[Nombre]` and `[dominio]`; photos are drawn shapes, not real images.
