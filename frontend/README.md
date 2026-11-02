# Frontend

Next.js app: the Neitor AI landing page (`/`) and the onboarding wizard opened from WhatsApp (`/o/[token]`). Planned, not built yet: the read-only dashboard (`/b/[token]`, T35) and the WhatsApp simulator used for development and as the demo fallback (`/dev/chat`, T22).

- Design: [docs/design/web-app.md](../docs/design/web-app.md)
- API contract: [docs/architecture/api.md](../docs/architecture/api.md)
- Setup: [docs/implementation/setup.md](../docs/implementation/setup.md)

Stack: Next.js (App Router, TypeScript), Tailwind CSS, shadcn/ui, lucide-react, deployed on Vercel.

## Run

```bash
cp .env.example .env.local
npm install
npm run dev
npm run typecheck   # next typegen, then tsc (strict flags in tsconfig.json); CI runs it with npm run lint
```

Until the backend serves the onboarding endpoints (T24), set `ENABLE_MOCK_API=true` and `NEXT_PUBLIC_API_URL=http://localhost:3000/mock-api` in `.env.local`: `lib/mock-backend.ts` implements the [onboarding contract](../docs/architecture/api.md#onboarding-web-wizard) in memory. Any token works (`/o/demo`); `/o/vencido` shows the expired-link screen.

## Layout

- `app/page.tsx` + `components/landing/`: the landing page, in Rioplatense Spanish like the bot and the wizard, built as one WhatsApp-style thread with Neitor (design: [canvas](https://claude.ai/artifact/4ghMvD3UL9q5x3E4P1Fbai), Option A). Server components except `approval-demo.tsx`, the hero's working Approve / Change buttons. Its colors are the `ld-*` tokens in `app/globals.css`; every CTA opens `NEXT_PUBLIC_WHATSAPP_URL` with "Hola Neitor" typed in (`lib/whatsapp.ts`).
- `app/o/[token]/`: the onboarding wizard route (loads `OnboardingState` on the server, `?step=` picks the screen).
- `components/onboarding/`: wizard shell, one file per step under `steps/`, the photo upload queue. The wizard reuses the landing's chat primitives (`Bubble`, `Display`, `NeitorAvatar`) and its palette, mapped onto the shadcn tokens in `app/globals.css`. `lib/categories.ts` holds the per-category examples, audiences and brand words; step order and resume logic are in `lib/onboarding.ts` ([ADR 0032](../docs/decisions/0032-instagram-first-onboarding.md)).
- `lib/api.ts`: REST client; Zod schemas (written by hand from `api.md`) check every response and give the types. `lib/upload.ts`: signed-URL uploads.
- `components/ui/`: shadcn/ui components, restyled to the tokens in [web-app.md](../docs/design/web-app.md#visual-language) (the landing palette), with a `cta` button variant for the orange call to action.
- `app/api/render/` + `lib/post-render/`: the post slide renderer ([ADR 0029](../docs/decisions/0029-designed-slides-ai-scene-code-layout.md)). The backend POSTs one slide's spec and gets a 1080×1350 JPEG, rendered by Takumi without a browser. Template families are in `lib/post-render/families/`, text fitting and photo legibility in `lib/post-render/design.ts`, the brand font pairs (OFL) in `lib/post-render/fonts/` ([ADR 0035](../docs/decisions/0035-art-director-design-rules-and-design-critic.md)). Contract: [integrations.md § Slide renderer](../docs/architecture/integrations.md#slide-renderer-takumi-on-vercel). With `ENABLE_TEMPLATE_PREVIEW=true`, `/dev/post-templates` shows every family and layout over sample copy, per sample brand.

## Deploy

The frontend runs on Vercel ([ADR 0004](../docs/decisions/0004-frontend-nextjs-vercel.md)): project `neitorai` in the `guidodinellos-projects` team (Hobby), production at `https://neitorai.vercel.app` (the old `https://build101-khaki.vercel.app` redirects to it with a 308). Operate it with the Vercel CLI (`npm i -g vercel`, `vercel login`) or the [`vercel-cli`](../.claude/skills/vercel-cli/SKILL.md) skill.

### How it deploys

- **Push to `main`** deploys production; every other pushed branch gets a preview deployment. The project is connected to GitHub `guidodinello/build101`.
- **Manual deploy** from the repo root: `vercel link --yes --project build101 --scope guidodinellos-projects` once, then `vercel deploy --prod`. Run both from the repo root and not from `frontend/`: the project's root directory is `frontend`, so a link or upload from inside `frontend/` fails with "Root Directory frontend does not exist".
- `vercel link` appends `.vercel` and `.env*` to the root `.gitignore`; drop the `.env*` line, it would hide `.env.example`.

### Project settings

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Framework preset | Next.js (default build, output and install commands) |
| Node.js | 24.x |
| Production branch | `main` |

### Environment variables

Set for Production and Preview (`vercel env add KEY production`, value on stdin). `NEXT_PUBLIC_*` values are inlined at build time, so a change needs a redeploy.

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | the Railway backend, `https://backend-production-6e67.up.railway.app` |
| `SUPABASE_URL` | the Supabase project URL, same as the backend's; read at build time for the CSP, and the Vercel build fails without it |
| `NEXT_PUBLIC_WHATSAPP_URL` | `https://wa.me/56920403095`, the shared Kapso sandbox number (same as the backend's `WHATSAPP_BOT_NUMBER`) |
| `ENABLE_MOCK_API` | `false` (the mock also answers 404 whenever `VERCEL_ENV` is `production`) |
| `NEXT_PUBLIC_DEV_TOKEN` | unset (the simulator is not used in production) |
| `RENDER_SECRET` | a random secret, the same as the backend's `RENDERER_SECRET`; without it `/api/render` answers 503 |
| `ENABLE_TEMPLATE_PREVIEW` | `false` |

### Security headers

`next.config.ts` sets `Content-Security-Policy`, `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff` on every route, and `Referrer-Policy: no-referrer` on `/o/*` (the onboarding token is in the path). The CSP allows `img-src` / `connect-src` only for `'self'`, the origins of `NEXT_PUBLIC_API_URL` and `SUPABASE_URL`, and `blob:` / `data:` images. Preview deployments also allow the [Vercel Toolbar hosts](https://vercel.com/docs/vercel-toolbar/managing-toolbar#using-a-content-security-policy). Scripts keep `'unsafe-inline'`: a nonce CSP would force dynamic rendering and rule out `cacheComponents`, so inline-script injection is not blocked. A new external host (an image CDN, an analytics script) needs an entry there.

The backend must list the Vercel domain in `FRONTEND_URL` and `FRONTEND_ORIGINS` ([backend/README.md](../backend/README.md#environment-variables)), or magic links point at localhost and browser calls fail CORS.
