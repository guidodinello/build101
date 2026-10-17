# Web app design

The web app is a **side door**. Owners spend 95% of their time in WhatsApp. The web exists for what WhatsApp can't do well: forms, bulk uploads, OAuth, and keeping the Catalog and Brand assets tidy. It must feel like a continuation of the chat: mobile, friendly, Spanish, one thing per screen. The more catalog and content the Owner uploads, the better the Posts and Reels get ([ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md)), so uploading must be effortless.

## Principles

1. **Mobile first, phone only in practice.** Design at 390×844; desktop is a centered 480 px column.
2. **One question per screen** in the wizard. Big tap targets (≥ 48 px), sticky bottom primary button.
3. **Autosave** every step; returning to the link resumes where the owner left.
4. **No jargon**: "Conectá tu Instagram", not "OAuth"; "Tu marca", not "Brand Brain"; "Tu catálogo", "Tus fotos y videos", "Promos", not "Catalog", "Brand assets", "Offers".
5. **Always a way back to WhatsApp** (header link on every screen).
6. **Rioplatense copy** with the same voice as the bot (see [../product/conversation-design.md](../product/conversation-design.md)).

## Stack and UI kit

- Next.js (App Router) + TypeScript, deployed on Vercel.
- Tailwind CSS + **shadcn/ui** components (Button, Input, Textarea, Select, Slider, RadioGroup, Checkbox, Card, Progress, Badge, Toast/Sonner, Skeleton, Tabs, Sheet, Dialog, AlertDialog, Command (product picker), Calendar + Popover (Offer dates), ToggleGroup).
- `lucide-react` icons. No other UI libraries.
- Data: `fetch` wrappers in `lib/api.ts` + React Server Components for initial load, client components for the wizard steps and dashboard edits. No global state library; the wizard keeps state in the URL (`?step=`) + server, and the dashboard keeps the active tab and filters in the URL (`?tab=contenido&product=…`).
- Uploads: `tus-js-client` for resumable uploads straight to Supabase Storage (see [Uploads](#uploads)); no file ever goes through Next.js.

## Visual language

| Token | Value | Use |
|---|---|---|
| `--background` | `#FAF7F2` (warm off-white) | Page |
| `--foreground` | `#1F1B16` | Text |
| `--primary` | `#1F6F5C` (deep green, WhatsApp-adjacent but not WhatsApp green) | Primary buttons, progress |
| `--primary-foreground` | `#FFFFFF` | |
| `--accent` | `#F2B84B` (warm amber) | Highlights, "listo" states |
| `--muted` | `#EFE9E0` | Cards, inputs background |
| `--muted-foreground` | `#6B6257` | Helper text |
| `--destructive` | `#C2410C` | Errors |
| `--radius` | `14px` | Cards, buttons, inputs |
| Font | Inter (UI), with `font-feature-settings: "ss01"` | |

Dark mode: not needed for the demo (owners open it from WhatsApp in daylight). Define tokens as CSS variables anyway so it can be added.

Tone of illustrations: none. Use the owner's own photos and logo as soon as they're uploaded. Seeing their brand appear is the delight moment.

## Screens

### `/o/[token]`: onboarding wizard

Header (all steps): small logo of the product · "Paso 2 de 6" · progress bar · "Volver a WhatsApp" link (wa.me).

```text
┌──────────────────────────────┐
│ ◀   Paso 1 de 6   ▓▓░░░░░░  │
│                              │
│ Contanos de tu negocio 🏪    │
│                              │
│ ¿Cómo se llama?              │
│ ┌──────────────────────────┐ │
│ │ Muebles Ramírez          │ │
│ └──────────────────────────┘ │
│ ¿De qué rubro es?            │
│ [Muebles y deco         ▾]   │
│ Contalo en una frase         │
│ ┌──────────────────────────┐ │
│ │ Muebles de madera maciza │ │
│ │ hechos a mano en Mvd     │ │
│ └──────────────────────────┘ │
│ ¿Dónde están?                │
│ [Montevideo              ]   │
│ Instagram (opcional)         │
│ [@mueblesramirez         ]   │
│                              │
│ ┌──────────────────────────┐ │
│ │       Siguiente →        │ │  ← sticky bottom
│ └──────────────────────────┘ │
└──────────────────────────────┘
```

| Step | Title | Content | Validation |
|---|---|---|---|
| 1 | Contanos de tu negocio 🏪 | name, category (Select), one-liner (Textarea, 120 chars), location, IG handle | name, category, one-liner required |
| 2 | ¿Qué es lo que más vendés? | Product cards, no upper limit: name, short description, price (optional). "+ Agregar otro". Hint: "Podés sumar todo tu catálogo después desde tu panel." | ≥ 1 product |
| 3 | Tu marca 🎨 | Logo dropzone → after upload shows the logo + **detected color swatches** (tap to edit with a color input, "+" to add); "3 palabras que usarían tus clientes para describirte" (3 inputs) | colors ≥ 1 (defaults if no logo) |
| 4 | Tus fotos y videos 📸🎬 | Grid uploader (camera roll multi-select, photos and videos together). Thumbnails with ✕; videos show a ▶ badge and their duration ("0:24"). Hint: "Productos, el taller, el equipo, videos cortos. Mientras más, mejor." Counter "12 fotos · 3 videos" (no cap) | ≥ 3 photos |
| 5 | ¿Cómo querés que suene? | Questionnaire, one card per question (see [../product/user-flows.md](../product/user-flows.md#flow-2--web-onboarding-form)): chips for options, sliders with labels at both ends | goal, posts/week, emoji required |
| 6 | Conectá tu Instagram | Explanation (2 lines: "Lo usamos solo para publicar lo que vos apruebes"), big button "Conectar Instagram" → redirects to Zernio; on return shows ✅ @handle. Secondary: "Lo hago después" | none |
| 7 | ¡Listo! 🎉 | "Ya tenemos todo. En un minuto te escribimos por WhatsApp con lo que entendimos de tu marca." + big "Volver a WhatsApp" button | calls `/complete` on mount (idempotent) |

Upload UX: see [Uploads](#uploads); the wizard and the dashboard share the same uploader component.

Error states: expired/invalid token → friendly screen "Este link venció. Escribinos 'link' por WhatsApp y te mandamos uno nuevo." (the onboarding router handles "link").

### Uploads

Shared by wizard step 4 and the dashboard's Contenido tab.

- Accepted: photos `image/jpeg`, `image/png`, `image/webp`, `image/heic` up to **10 MB**; videos `video/mp4`, `video/quicktime` (MOV) up to **300 MB**. Anything else gets a friendly inline error on its thumbnail, never a blocking dialog: "Este video pesa más de 300 MB. Probá mandar uno más corto 🙏" / "Este archivo no lo podemos usar. Subí fotos o videos."
- Flow per file: `POST …/uploads` → signed Supabase URL → upload from the browser (resumable TUS for files over 6 MB, plain PUT below) → `POST …/assets/{id}/complete`. The backend never receives the file bytes. Endpoints in [../architecture/api.md](../architecture/api.md).
- Show each thumbnail immediately (object URL; for videos, the first frame via a hidden `<video>`), with a **per-file progress ring** overlay. Up to 3 files upload in parallel; the rest queue.
- Failure: the thumbnail turns red with "Reintentar". Resumable uploads continue where they stopped after a network drop or the phone locking.
- Leaving the page while uploads are running shows "Todavía estamos subiendo 3 archivos. ¿Salir igual?".
- After `complete`, the thumbnail shows a small "Mirando…" chip until the Asset Analyst finishes; then videos that can become a Reel get the **"Ideal para Reel"** badge.
- HEIC is converted server-side after upload.

### `/b/[token]`: dashboard (Must)

The Owner's panel to see what the Agency is doing and to feed it: Catalog, photos and videos, and Promos. Opened from the "Abrí tu panel" button the bot sends (a `dashboard` magic link valid 7 days). Editable, mobile, four tabs in a **bottom tab bar** (thumb-reachable), each tab one screen:

| Tab | Shows | Edits |
|---|---|---|
| **Inicio** | This week's Posts with status badges (Reels carry a ▶ badge), brand summary | Nothing (approval stays in WhatsApp) |
| **Catálogo** | Products, searchable, with a thumbnail from a linked photo | Add, edit, archive Products |
| **Contenido** | Grid of photos and videos, filter by Product, "Ideal para Reel" filter | Upload, link Products, add a hint, archive |
| **Promos** | Active, draft and past Offers | Create, edit, activate, archive Offers |

Header (all tabs): logo + business name · "Volver a WhatsApp" link.

#### Inicio

```text
┌──────────────────────────────┐
│ [logo] Muebles Ramírez   💬  │  ← 💬 = Volver a WhatsApp
│ Instagram ✅ @mueblesramirez  │
├──────────────────────────────┤
│ Esta semana                  │
│ ┌────┐ Mar 21 · Mesa Nórdica │
│ │img │ ● Programado 19:00    │
│ └────┘                       │
│ ┌────┐ Jue 23 · El taller    │
│ │ ▶  │ Reel ● Esperando apr. │
│ └────┘                       │
├──────────────────────────────┤
│ Tu marca                     │
│ Cercanos · cálidos · artesan.│
│ Pilares: A medida · Taller · │
│ Ideas para tu living         │
│ ■ ■ ■  (colores)             │
├──────────────────────────────┤
│ 23 productos · 64 fotos ·    │
│ 7 videos  [Sumar más →]      │  ← goes to Contenido
├──────────────────────────────┤
│ Inicio Catálogo Cont. Promos │
└──────────────────────────────┘
```

Status badges: Generando (gray), Esperando aprobación (amber), Aprobado (blue), Programado (green outline), Publicado (green, links to IG), Descartado (muted), Error (red). A Reel adds a "Reel" text badge next to the status (never color alone).

#### Catálogo

```text
┌──────────────────────────────┐
│ Tu catálogo          23 📦   │
│ [🔍 Buscar producto        ] │
│ ┌────┐ Mesa Nórdica          │
│ │img │ $ 18.900 · Comedor    │
│ └────┘ 4 fotos · 1 video   › │
│ ┌────┐ Silla Oslo            │
│ │img │ Sin precio · Sillas   │
│ └────┘ 2 fotos             › │
│ ┌────┐ Rack TV Roble         │
│ │ ?  │ Sin fotos todavía     │  ← nudge: "Sumá fotos"
│ └────┘                     › │
│                              │
│            ┌───────────────┐ │
│            │ + Agregar     │ │  ← floating button
│            └───────────────┘ │
├──────────────────────────────┤
│ Inicio Catálogo Cont. Promos │
└──────────────────────────────┘
```

- Tapping a Product or "+ Agregar" opens a bottom **Sheet**: name (required), description, price (free text, optional: "$ 18.900", "desde $ 4.500", "consultar"), category (Select with the business's existing categories + "Nueva…"), and its linked photos and videos with "+ Sumar fotos" (opens the uploader, links the new files to this Product).
- "Archivar producto" at the bottom of the Sheet, behind an **AlertDialog**: "¿Archivar Silla Oslo? No la vamos a usar en posts nuevos. Lo que ya está publicado no cambia." Nothing is deleted.
- Archived Products are hidden behind a "Ver archivados" link at the end of the list, with "Restaurar".

#### Contenido

```text
┌──────────────────────────────┐
│ Tus fotos y videos           │
│ [Todo ▾] [Ideal para Reel]   │  ← Product filter + toggle
│ ┌────┐┌────┐┌────┐           │
│ │img ││ ▶  ││img │           │
│ │    ││0:24││ ◔  │           │  ← ◔ = uploading
│ └────┘└────┘└────┘           │
│ ┌────┐┌────┐┌────┐           │
│ │img ││ ▶  ││img │           │
│ │    ││Reel││    │           │  ← Ideal para Reel
│ └────┘└────┘└────┘           │
│ ┌────┐┌────┐┌────┐           │
│ │img ││img ││img │           │
│ └────┘└────┘└────┘           │
│                     ┌──────┐ │
│                     │  ＋  │ │  ← multi-upload FAB
│                     └──────┘ │
├──────────────────────────────┤
│ Inicio Catálogo Cont. Promos │
└──────────────────────────────┘
```

- 3-column grid, newest first, infinite scroll. Videos show ▶ + duration; reel-suitable videos show "Reel".
- The FAB opens the camera roll multi-select (photos and videos); see [Uploads](#uploads).
- Tapping an item opens a **Sheet**: the photo or a playable video, the Agency's description ("Lo que vemos: mesa de roble en un living con luz natural"), linked Products as removable chips + "Vincular producto" (**Command** picker over the Catalog), an optional "¿Algo que debamos saber?" hint field, and for videos the "Ideal para Reel" reason or why not ("Es horizontal" / "Dura más de 90 segundos"). Frames saved from a video show "Sacada de un video".
- Links the Agency suggested and links the Owner set look the same; removing one is final (the Agency won't add it back).
- "Archivar" behind an AlertDialog: "No la vamos a usar en posts nuevos. Lo que ya está publicado o programado no cambia." Posts still in draft that use it get flagged for review.

#### Promos

```text
┌──────────────────────────────┐
│ Promos                       │
│ Activas                      │
│ ┌──────────────────────────┐ │
│ │ 🏷 15% en sillas          │ │
│ │ Promo · hasta dom 26      │ │
│ └──────────────────────────┘ │
│ ┌──────────────────────────┐ │
│ │ 📦 Combo comedor          │ │
│ │ Pack · Mesa + 4 sillas    │ │
│ │ $ 29.900 · sin fecha      │ │
│ └──────────────────────────┘ │
│ Borradores                   │
│ ┌──────────────────────────┐ │
│ │ ✏️ Envío gratis Mvd       │ │  ← from the chat, not confirmed
│ └──────────────────────────┘ │
│            ┌───────────────┐ │
│            │ + Nueva promo │ │
│            └───────────────┘ │
├──────────────────────────────┤
│ Inicio Catálogo Cont. Promos │
└──────────────────────────────┘
```

- Form (Sheet): type as a **ToggleGroup** "Promo" / "Pack (varios productos juntos)", title, products (Command picker; a pack needs ≥ 2), conditions (Textarea: "15% pagando en efectivo"), price (free text, optional), dates "Desde / Hasta" (Calendar in a Popover, both optional), and the primary button "Activar promo". "Guardar borrador" is secondary.
- Only active Offers are used by the Agency; the form says so under the button: "Solo usamos en tus posts las promos activas."
- Past Offers (after their end date) appear under "Terminadas", read-only, with "Repetir" (copies into a new draft).
- Archive behind an AlertDialog, same copy pattern as Products.

#### Link and error states

- Expired or invalid dashboard link → friendly screen: "Este link venció 🔒. Escribinos 'link' por WhatsApp y te mandamos uno nuevo." + big "Volver a WhatsApp" button.
- Empty states: Catálogo "Todavía no cargaste productos. Empezá por los que más vendés." · Contenido "Subí fotos y videos de tus productos, el taller, el equipo. Mientras más, mejor." · Promos "¿Tenés alguna promo o combo? Cargala y la usamos en tus posts."
- Every edit autosaves with a Sonner toast ("Guardado ✓"); failed saves keep the form open with "No se pudo guardar. Probá de nuevo."

### `/dev/chat`: WhatsApp simulator (Must)

Desktop layout used for development, rehearsal and as the stage fallback. It must look enough like WhatsApp that the demo still reads as "the owner is chatting".

```text
┌───────────────────────────────────────────┬─────────────────────────┐
│  ◀  Muebles Ramírez (sim-5f2a)   [Reset]  │ Debug                   │
│───────────────────────────────────────────│ state: active           │
│                     hola                ✓ │ awaiting: post_feedback │
│ ¡Hola! 👋 Soy ..., tu agencia ...         │ jobs:                   │
│                                           │  generate_post ✓ 38s    │
│ ┌───────────────┐                         │ agent_runs (latest 10)  │
│ │   [image]     │                         │  copywriter 6.1s 2.3k   │
│ │ 📝 Post para..│                         │  art_director 9.8s 4.1k │
│ │ [Aprobar]     │                         │  ...                    │
│ │ [Cambiar]     │                         │                         │
│ │ [Descartar]   │                         │                         │
│ └───────────────┘                         │                         │
│───────────────────────────────────────────│                         │
│ [📎] [ Escribí un mensaje...      ] [➤]   │                         │
└───────────────────────────────────────────┴─────────────────────────┘
```

- Bubbles: outbound (bot) left/white, inbound (owner) right/green `#D9FDD3`, background `#EFEAE2`, like WhatsApp.
- Interactive messages render buttons under the bubble; clicking sends a `button_reply`.
- 📎 lets you send an image (upload → URL → `{type: "image", url}`).
- Polls `GET /dev/sim/{phone}/messages?after=` every 1 s.
- Right panel (toggleable, hidden during demo): business state, recent jobs, recent agent runs with latency/tokens; click a run to see input/output JSON.
- Query param `?phone=` reuses an existing simulator business; "Reset" creates a fresh one.

## Accessibility and quality bar

- All inputs have labels; color is never the only status signal (badges have text).
- Contrast ≥ 4.5:1 for text (tokens above meet it on `--background`).
- Works on iOS Safari and Android Chrome (the in-app browser that WhatsApp opens links in).
