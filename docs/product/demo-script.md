# Demo script

~4 minutes. The furniture business owner (our teammate) plays themself on a real phone; the phone screen is mirrored on the projector. Fill in the placeholders once the materials are collected.

| Placeholder | Value |
|---|---|
| `{BUSINESS}` | Name of the teammate's furniture business |
| `{IG_HANDLE}` | Its Instagram handle |
| `{PRODUCT}` | One star product (e.g. a dining table) |
| `{PROMO}` | A real current promo |
| `{VIDEO}` | A short vertical video from the workshop (3–90 s), e.g. a chair being sanded |

## Setup before going on stage

- [ ] Backend deployed, `/health` OK; `PUBLISHER=zernio`; IG connected for `{BUSINESS}`.
- [ ] **Two businesses ready:**
  - *Live onboarding*: the presenter's phone is reset to `new` (`/dev/businesses/{id}/reset`).
  - *Seeded*: `{BUSINESS}` already `active` with a Brand Brain, an approved plan, a Catalog of real Products and `{VIDEO}` already analyzed in its library (from `/dev/seed/demo`), used if live onboarding is slow and for the dashboard beat.
- [ ] Wizard photos and logo already in the phone's camera roll, in an album.
- [ ] A fresh dashboard link for `{BUSINESS}` open in a second phone tab.
- [ ] `/dev/chat` open in a hidden browser tab (fallback channel).
- [ ] Backup video of the full flow ready to play.
- [ ] One older post and one older Reel already published by the system on `{IG_HANDLE}` (proof if a live publish fails).

## Script

### 0:00 – Problem (30 s)

Narrator:
> "{Owner} tiene una mueblería. Sabe que Instagram le trae clientes, pero entre el taller, los proveedores y las ventas no tiene tiempo de planear, escribir ni diseñar posts. Una agencia no le da el presupuesto. Pero WhatsApp lo usa todo el día."

### 0:30 – Onboarding (75 s)

1. Owner sends "Hola" → welcome → types `{BUSINESS}` → magic link arrives.
2. Opens the link: fills step 1 quickly (prefilled name), picks 3 products, uploads the logo (**colors appear automatically**, a visible "wow"), selects 8 photos, taps through the questionnaire, connects Instagram (already authorized; one tap), "Volver a WhatsApp".
3. Narrator while the Brand Brain generates: "Mientras tanto, un equipo de agentes está estudiando su marca: un analista mira cada foto, una estratega arma la identidad de la marca."
4. WhatsApp: brand summary arrives → owner reads one line aloud ("Cercanos, cálidos, artesanales… sí, somos nosotros") → `[Sí, es mi marca]`.

> Fallback: if the summary takes > 60 s, switch to the seeded business ("este es el que preparamos ayer con los mismos datos").

### 1:45 – Catalog and material (20 s)

1. Owner writes "¿dónde veo todo?" → dashboard link → opens the seeded `{BUSINESS}` dashboard: the Catalog with their real Products and `{VIDEO}` in the library, tagged with the Product it shows.
2. Narrator: "Todo lo que sube, fotos, videos, productos, el equipo lo usa. Cuanto más sube, mejor le sale."

### 2:05 – Weekly plan + Reel (40 s)

1. Back in WhatsApp: `[Dale]` → plan of 3 Posts arrives, one of them a 🎬 Reel → narrator points out it uses their real Products and promo → `[Aprobar plan]`.
2. The first preview arrives (image + caption + buttons). Narrator: "Foto real del taller, colores y logo de la marca, texto en su tono."
3. The Reel preview arrives: `{VIDEO}` with its caption → `[Aprobar]` → `[Publicar ahora]` (Instagram processes it while the demo goes on).

### 2:45 – Change request (30 s)

1. On the image Post: `[Cambiar]` → owner types: "más corto y decí que hay envío gratis en Montevideo" → revised Post arrives in ~20–30 s.

### 3:15 – Ad-hoc + publish (30 s)

1. Owner types: "hacé un post para la promo del finde: {PROMO}" → "¡Dale! Lo armo ⏳" → preview with the `promo_band` template → `[Aprobar]` → `[Publicar ahora]` → "¡Publicado! 🎉 <link>".
2. Open `{IG_HANDLE}` on the projector: **the Post and the Reel are live.**

> Fallback: if the Reel is still processing, show the pre-published Reel and its "¡Publicado!" message from rehearsal.

### 3:45 – Close (15 s)
>
> "Vos trabajás desde WhatsApp; la web es solo para cargar tus productos, fotos y videos. Una agencia de marketing que vive en el WhatsApp de cada emprendedor, y que no publica nada sin su sí. Hoy es marketing; mañana, proveedores, pedidos y seguimientos."

## What to say if asked

- **"¿Y si el agente se equivoca?"** Nothing is published without the owner's tap; approval is enforced in code, not left to the AI.
- **"¿Inventa cosas?"** The agents only use facts the owner gave; prices and promos only appear if the owner defined them as an Offer or mentioned them; there are automated checks for that.
- **"¿Editan los videos?"** Not yet: a Reel is the owner's own video, published as-is with a caption and a cover chosen by the agents.
- **"¿Cómo escala?"** One team of specialized agents shared by all businesses, personalized by each business's brand profile; adding a business costs no setup.
- **"¿Modelo de negocio?"** Monthly subscription by number of posts; the data model already has plans and quotas.
