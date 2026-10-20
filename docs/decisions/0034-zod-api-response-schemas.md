# 0034: Check backend responses in the frontend with Zod schemas

- Date: 2026-10-19
- Status: proposed

## Context

`frontend/lib/api.ts` cast every backend response (`response.json() as Promise<T>`) and read the error envelope from `any`. The TypeScript types were written by hand from [architecture/api.md](../architecture/api.md) ([ADR 0004](0004-frontend-nextjs-vercel.md)), so nothing checked them at runtime: a backend contract change surfaced as a crash deep inside a component, far from its cause. This is finding 4 of the type health audit (story #83, issue #88).

Alternatives considered:

- **Generate the types from FastAPI's OpenAPI schema.** One source of truth with the Pydantic models, but it only produces types: the response is still trusted, so a mismatch still crashes late. It also adds a build step and needs a running backend or a committed spec.
- **Keep the casts.** No new dependency, and no protection.

## Decision

Use [Zod](https://zod.dev) 4 in `frontend/lib/api.ts`:

- One Zod schema per backend response the client reads; the TypeScript types are `z.infer` of the schemas, so a payload shape is defined once.
- Every response is parsed with `safeParse` at the boundary. A body that doesn't match throws `ApiError(status, "invalid_response", <generic message>, { cause })`, the error type callers already handle through `messageOf` and `instanceof ApiError`. The Zod issues stay in `cause` for debugging. `.parse()` would throw a foreign `ZodError` that callers don't recognize.
- The error envelope (`{"error": {"code", "message"}}`) is parsed with a schema too; a malformed one falls back to code `unknown` and the generic message, as before.
- Schemas mirror the Pydantic models in `backend/app/onboarding/schemas.py` by hand, field for field (`.nullable()` where the backend returns `X | None`). `api.md` stays the contract. Request types stay hand-written: the client sends them and never parses them, so a schema would add no runtime check.
- Import as `import * as z from "zod"`; pin the exact version.

## Consequences

- A contract change fails in `lib/api.ts` with a typed error, not inside a component. The mock API ([`app/mock-api/`](../../frontend/app/mock-api/)) has to keep returning shapes that pass the schemas.
- The schemas are a second hand-written copy of the Pydantic models, so a backend change means updating both. The runtime check is what makes that drift visible. Generating schemas from OpenAPI later is still possible and would replace only the schema definitions.
- Zod becomes a client dependency (a few KB gzipped).
- Zod was first pinned to exactly `4.6.5`, about five weeks old when added, as a supply-chain cooldown. On 2026-10-20 the pin moved to exactly `4.6.7` (8 days old), after checking it was published by `colinhacks` through the trusted GitHub Actions release workflow with SLSA provenance.
- A backend field added later is ignored (Zod strips unknown keys); a removed or retyped one fails.
- Supersedes the consequence in [ADR 0004](0004-frontend-nextjs-vercel.md) that REST types are written by hand.
