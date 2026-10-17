# Frontend

Next.js app: the onboarding wizard opened from WhatsApp (`/o/[token]`), the read-only dashboard (`/b/[token]`) and the WhatsApp simulator used for development and as the demo fallback (`/dev/chat`).

- Design: [docs/design/web-app.md](../docs/design/web-app.md)
- API contract: [docs/architecture/api.md](../docs/architecture/api.md)
- Setup: [docs/implementation/setup.md](../docs/implementation/setup.md)

Stack: Next.js (App Router, TypeScript), Tailwind CSS, shadcn/ui, lucide-react, deployed on Vercel.

## Run

```bash
cp .env.example .env.local
npm install
npm run dev
```

Until the backend serves the onboarding endpoints (T24), set `ENABLE_MOCK_API=true` and `NEXT_PUBLIC_API_URL=http://localhost:3000/mock-api` in `.env.local`: `lib/mock-backend.ts` implements the [onboarding contract](../docs/architecture/api.md#onboarding-web-wizard) in memory. Any token works (`/o/demo`); `/o/vencido` shows the expired-link screen.

## Layout

- `app/o/[token]/`: the onboarding wizard route (loads `OnboardingState` on the server, `?step=` picks the screen).
- `components/onboarding/`: wizard shell, one file per step under `steps/`, the photo upload queue.
- `lib/api.ts`: REST client and types, written by hand from `api.md`. `lib/upload.ts`: signed-URL uploads.
- `components/ui/`: shadcn/ui components, restyled to the tokens in [web-app.md](../docs/design/web-app.md#visual-language).
