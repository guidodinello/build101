# Backend

FastAPI service: WhatsApp webhook, conversation routing, orchestrator + specialist agents (Gemini, [ADR 0023](../docs/decisions/0023-gemini-text-llm.md)), background jobs, AI image generation for Posts and carousels (Gemini, [ADR 0018](../docs/decisions/0018-ai-image-generation-service.md), [ADR 0019](../docs/decisions/0019-image-provider-gemini.md), [ADR 0022](../docs/decisions/0022-carousels-in-mvp.md)) and publishing (Zernio).

- Architecture: [docs/architecture/overview.md](../docs/architecture/overview.md)
- Agents: [docs/architecture/agents.md](../docs/architecture/agents.md)
- API: [docs/architecture/api.md](../docs/architecture/api.md)
- Setup: [docs/implementation/setup.md](../docs/implementation/setup.md)

Stack: **Python + FastAPI**, uv project rooted here ([ADR 0001](../docs/decisions/0001-backend-python-fastapi.md)), with SQLAlchemy 2 (async) + asyncpg, Pydantic v2, `google-genai`, `google-genai` and Supabase ([ADR 0003](../docs/decisions/0003-database-supabase-sqlalchemy.md)).

Commands run from this folder (`uv run ruff check .`, `uv run pytest tests/ -v`); see [`.claude/rules/python.md`](../.claude/rules/python.md).

## What exists today

- `app/main.py`: `/health` (`uv run uvicorn app.main:app --reload`).
- `app/imagegen/`: `ImageGenPort` with the Gemini and mock adapters, selected by `IMAGE_GEN`.
- `app/media/images.py`: reference photo normalization and the 1080×1350 resize.
- `app/carousel/`: carousel schemas, slide prompts and `CarouselGenerator` (cover first, other slides anchored on it).
- `app/channels/`: `ChannelPort` with the Kapso adapter, `POST /webhooks/whatsapp` (signature check, dedupe, background handling) and an echo handler until the conversation router (T23) exists.

Generate a carousel from a copy + brief spec without the database or the agents:

```bash
cp .env.example .env   # set IMAGE_GEN=gemini and GEMINI_API_KEY for real calls
uv run python -m app.carousel.cli --spec tests/fixtures/carousel_spec.json \
  --photos ~/demo/photo1.jpg ~/demo/photo2.jpg --out out/carousel [--slides 1]
```

It writes `slide-N.jpg`, each slide's prompt and a `report.json` with latency, raw size and token usage per call. Live tests run with `uv run pytest -m live` (skipped without `GEMINI_API_KEY`).

Write this week's Niche Report ([ADR 0025](../docs/decisions/0025-weekly-niche-report.md)) for a Business in a known niche; set `NICHE_REPORT_PATH=out/niche-report.json` and post generation gets its insights as trend notes:

```bash
uv run python -m app.agents.niche_cli --niche curated-wood-furniture-uy --name "Roble & Co" \
  --category "muebles de madera maciza" --about "Mesas y aparadores a medida" --out out/niche-report.json
```

It needs `GEMINI_API_KEY` from a project with billing (Google Search grounding isn't on the free tier) and takes 30–100 s.
