# Demo script

~4 minutes. The furniture business owner (our teammate) plays themself on a real phone; the phone screen is mirrored on the projector. Fill in the placeholders once the materials are collected. Scope: a short onboarding, then one post from request to published ([ADR 0016](../decisions/0016-demo-scope-one-post.md)).

| Placeholder | Value |
|---|---|
| `{BUSINESS}` | Name of the teammate's furniture business |
| `{IG_HANDLE}` | Its Instagram handle |
| `{PRODUCT}` | A new or star piece the owner wants to show (e.g. a coffee table) |
| `{PHOTOS}` | 2 photos of `{PRODUCT}` on the phone, one wide and one detail |
| `{REQUEST}` | The owner's request in their own words, e.g. "me llegó esta mesa ratona nueva 😍 armame algo para subir" |

## Setup before going on stage

- [ ] Backend deployed, `/health` OK; `PUBLISHER=zernio`; IG connected for `{BUSINESS}`.
- [ ] **Two businesses ready:**
  - *Live onboarding*: the presenter's phone is reset to `new` (`/dev/businesses/{id}/reset`).
  - *Seeded*: `{BUSINESS}` already `active` with a pre-generated Brand Brain (from `/dev/seed/demo`), used if brand generation is slow.
- [ ] Wizard photos and logo in the phone's camera roll, in an album; `{PHOTOS}` in a second album.
- [ ] `/dev/chat` open in a hidden browser tab (fallback channel).
- [ ] Backup video of the full flow ready to play.
- [ ] One older post already published by the system on `{IG_HANDLE}` (proof if the live publish fails).
- [ ] Rehearsed `{REQUEST}` and the answer to the one question the bot is likely to ask ("novedad, y que se luzca la madera").

## Script

### 0:00 – Problem (30 s)

Narrator:
> "{Owner} tiene una mueblería. Sabe que Instagram le trae clientes, pero entre el taller, los proveedores y las ventas no tiene tiempo de pensar, escribir ni diseñar posts. Una agencia no le da el presupuesto. Pero WhatsApp lo usa todo el día."

### 0:30 – Onboarding (75 s)

1. Owner sends "Hola" → welcome → types `{BUSINESS}` → magic link arrives.
2. Opens the link: step 1 (prefilled name), 2–3 products, uploads the logo (**colors appear automatically**, a visible "wow"), selects 6–8 photos, taps through the questionnaire, connects Instagram (already authorized; one tap), "Volver a WhatsApp".
3. Narrator while the Brand Brain generates: "Mientras tanto, un equipo de agentes está estudiando su marca: un analista mira cada foto, una estratega arma la identidad de la marca."
4. WhatsApp: brand summary arrives → owner reads one line aloud ("Cercanos, cálidos, artesanales… sí, somos nosotros") → `[Sí, es mi marca]` → "¡Listo, ya conozco tu marca! ¿En qué te puedo ayudar hoy?"

> Fallback: if the summary takes > 60 s, switch to the seeded business ("este es el que preparamos ayer con los mismos datos").

### 1:45 – Asking for a post (90 s)

1. Owner sends `{PHOTOS}` + `{REQUEST}`. Narrator: "Sin menús ni formularios: le escribe como a una persona."
2. Bot asks one question ("¿La mostramos como novedad o tiene algún precio de lanzamiento?") → owner answers in a few words.
3. Bot: "Dale, lo armo con la foto del detalle ⏳". Narrator, while it works (duration to measure with the real image service): "Una redactora escribe en su tono, un director de arte elige sus fotos y le pide a un generador de imágenes varias versiones con los colores de su marca."
4. The variations arrive ([ADR 0018](../decisions/0018-ai-image-generation-service.md)); the owner picks one ("la 2"; how the pick works is still open, see [open questions](../open-questions.md#post-images-generated-by-ai-adr-0018)) → preview: that image + caption + `[Aprobar] [Cambiar] [Descartar]`. Narrator: "Su producto real, su marca, su forma de hablar."

### 3:15 – Publish (20 s)

1. Owner writes "subila" (no button needed) → "arriba ✅" → "¡Publicado! 🎉 <link>".
2. Open `{IG_HANDLE}` on the projector: **the Post is live.**

> Fallback: if publishing fails, switch `PUBLISHER=mock`, show the generated Post and the "would publish" log, and open the pre-published post from rehearsal.

### 3:35 – Close (20 s)
>
> "Vos le escribís como a una persona de tu equipo; ella arma y publica, y nada sale sin tu sí. Una agencia de marketing que vive en el WhatsApp de cada emprendedor. Hoy es marketing; mañana, proveedores, pedidos y seguimientos."

## What to say if asked

- **"¿Y si el agente se equivoca?"** Nothing is published without the owner's yes, by tap or in writing; approval is enforced in code, not left to the AI.
- **"¿Inventa cosas?"** The agents only use facts the owner gave; prices and promos only appear in the caption, and only if the owner mentioned them; there are automated checks for that. The images are generated from the owner's real photos with prompts that forbid text, prices and logo changes, and the owner picks and approves every one ([ADR 0018](../decisions/0018-ai-image-generation-service.md)).
- **"¿Qué más hace?"** Proposes ideas when you don't know what to post, plans the week if you ask, schedules ("subilo mañana a la tarde") and takes changes in your own words.
- **"¿Hace Reels?"** Next: Reels from the owner's own videos, published as-is with a caption and a cover chosen by the agents ([ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md)).
- **"¿Cómo escala?"** One team of specialized agents shared by all businesses, personalized by each business's brand profile; adding a business costs no setup.
- **"¿Modelo de negocio?"** Monthly subscription by number of posts; the data model already has plans and quotas.
