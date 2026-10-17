# Gemini API as the LLM provider

Question: what changes if the agents run on Google's Gemini API instead of Claude ([ADR 0010](../decisions/0010-anthropic-sdk-own-orchestration.md))? Which model, SDK and API shape, and what it costs.

Read on 2026-10-17 from Google's official docs (links inline). Models, prices and limits change, so re-check before relying on them. Outcome: [ADR 0023](../decisions/0023-gemini-text-llm.md).

## SDK and API

- Official Python SDK: **`google-genai`** (latest 2.31.0, released 2026-10-14, Python ≥ 3.10, [PyPI](https://pypi.org/project/google-genai/)). The old `google-generativeai` is deprecated since 2025-11-30 and must not be used ([libraries](https://ai.google.dev/gemini-api/docs/libraries)).
- `genai.Client()` reads `GEMINI_API_KEY` or `GOOGLE_API_KEY`; if both are set, `GOOGLE_API_KEY` wins, so set only one. Async methods live under `client.aio`; close with `await aclient.aclose()` or `async with Client().aio as aclient` ([python-genai README](https://github.com/googleapis/python-genai)).
- Keys come from Google AI Studio: <https://aistudio.google.com/api-keys> ([quickstart](https://ai.google.dev/gemini-api/docs/quickstart)).
- Current docs are written for the **Interactions API**: `client.interactions.create(model=..., input=...)` → `interaction.output_text` ([quickstart](https://ai.google.dev/gemini-api/docs/quickstart)). `generate_content` still exists, but the guides below only show Interactions.

## Features we rely on

| Need (from [agents.md](../architecture/agents.md)) | Gemini equivalent |
|---|---|
| Structured output for specialists | `response_format={"type": "text", "mime_type": "application/json", "schema": Model.model_json_schema()}`, then `Model.model_validate_json(interaction.output_text)`. Subset of JSON Schema: `string`, `number`, `integer`, `boolean`, `object`, `array`, `null`; `enum`, `required`, `additionalProperties`, `minItems`/`maxItems`; very large or deeply nested schemas may be rejected ([structured output](https://ai.google.dev/gemini-api/docs/structured-output)) |
| Manual tool-use loop for the orchestrator | Declare `{"type": "function", "name", "description", "parameters"}` in `tools`; read the `function_call` step from `interaction.steps`; run it in our code; send back a `function_result` step with the same `call_id`. The model never runs the function itself ([function calling](https://ai.google.dev/gemini-api/docs/function-calling)) |
| Conversation history persisted in our DB | Stateless mode: `store=False` and resend the full history. **All `thought` blocks must be resent exactly as received**, since they carry the thought signatures ([thinking](https://ai.google.dev/gemini-api/docs/thinking)). Stateful mode (`previous_interaction_id`) keeps history on Google's side instead |
| Per-agent "effort" | `generation_config={"thinking_level": ...}`. `gemini-3.8-flash`: low / medium / high, default medium. No documented way to turn thinking off. `max_output_tokens` counts thinking + output, so lower `thinking_level` instead of capping tokens ([thinking](https://ai.google.dev/gemini-api/docs/thinking)) |
| Image input | Supported (multimodal input) |
| Video input | **Native**, audio track included. 1 frame/s by default (`processing.fps` adjustable), ~100 tokens/s at low resolution, ~300 at high. Files API up to 2 GB (free) / 20 GB (paid); inline under ~20 MB. Formats include mp4, mov, webm, 3gpp ([video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)) |
| Prompt caching | Context caching, priced per model (table below) |

## Models and prices

Per 1M tokens, paid tier ([models](https://ai.google.dev/gemini-api/docs/models), [pricing](https://ai.google.dev/gemini-api/docs/pricing)):

| Model | Positioning | Free tier | Input | Output |
|---|---|---|---|---|
| `gemini-4-argon` | Flagship reasoning, 1M context | No | US$2.00 (US$4.00 from 2026-12-01) | US$10.00 (US$20.00 from 2026-12-01) |
| `gemini-3.8-flash` | Strongest Flash, built for agents | Yes | US$0.75 (US$1.50 from 2027-01-01) | US$3.75 (US$7.50 from 2027-01-01) |
| `gemini-3.5-flash-lite` | Fastest and cheapest | Yes | US$0.30 | US$2.50 |

- **Free-tier content is used to improve Google products; paid-tier content is not** ([pricing](https://ai.google.dev/gemini-api/docs/pricing)). Owners' business data should run on the paid tier once real businesses use it.
- Free-tier rate limits are per project and only shown in AI Studio; preview models have tighter limits. Billing set up in AI Studio moves the project to Tier 1, usually at once ([rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)).
- Image generation is available on the same key (Nano Banana models, e.g. `gemini-3.1-flash-image`) ([models](https://ai.google.dev/gemini-api/docs/models)), relevant to the optional `ImageGenPort` in [ADR 0009](../decisions/0009-branded-templates-over-real-photos.md).

## Not verified

- Async Interactions call (`await client.aio.interactions.create(...)`): the README says `client.aio` mirrors every sync module but shows no Interactions example.
- Combining structured output with function calling in one call: preview feature for Gemini 3 models only.
- Exact free-tier RPM / RPD for `gemini-3.8-flash` (check AI Studio before the hackathon).
- A server-side refusal fallback like the one in agents.md: no equivalent found; handle blocked or empty responses in our code.
