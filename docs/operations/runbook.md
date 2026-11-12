# Pilot support runbook

What to do when a pilot Owner says the bot went quiet, a Post didn't arrive, or something else broke. One entry per symptom: the symptom, how to check, the fix, and the message to send the Owner. Written against `main` as of 2026-10-29 ([#184](https://github.com/guidodinello/build101/issues/184), audit finding DOC-6 in [docs-process.md](../research/audit-2026-10/docs-process.md)).

There are no automatic alerts yet: error tracking, uptime and heartbeat alerts are [#183](https://github.com/guidodinello/build101/issues/183). Until it lands, every check below uses today's tools. Add the alert to each entry once #183 has one.

## Before any entry

- **Logs**: `railway logs --service backend` (or the dashboard: project `build101`, service `backend`, Deployments, the active one, Logs). Railway tags every line `level=error`, even normal `INFO` lines, so read the message text ([backend README § Logs and checks](../../backend/README.md#logs-and-checks)). Phone numbers show as `***1234`, the last 4 digits.
- **Health**: `curl -sS https://<service>.up.railway.app/ready` gives `{"status":"ok","checks":{...},"commit":"<sha>"}`, or a 503 naming the failed check. `commit` is the deployed commit.
- **Database**: the Supabase dashboard, SQL editor. Find the Owner's Business with `select id, name, onboarding_state from businesses where owner_phone = '<digits>';`.
- **WhatsApp**: the Kapso dashboard, the number's webhooks and their delivery log.
- **Messages to the Owner** go from the team's own WhatsApp, or from Kapso's inbox on the bot number if the Owner shouldn't see a second number. Short, *vos*, no technical words ([conversation-design.md](../product/conversation-design.md)).

## Kapso webhook paused or with the wrong secret

- **Symptom**: the bot answers nobody. The bot's replies show no read ticks or typing.
- **How to check**:
  - Logs: every delivery is answered `"POST /webhooks/whatsapp HTTP/1.1" 401` (wrong secret), or no `queued inbound` lines show up at all when the Owner writes (webhook paused or pointing elsewhere).
  - Kapso dashboard: the number's "Message received" webhook is paused, points at a tunnel URL instead of the Railway domain, or its delivery log shows 401s.
- **Fix**:
  - Paused or wrong URL: resume the Railway webhook, and pause any tunnel webhook. Only one backend may answer the number ([backend README § Switching WhatsApp](../../backend/README.md#switching-whatsapp-between-railway-and-local-development)).
  - 401: each Kapso webhook has its own signing secret. Copy the Railway webhook's secret into `KAPSO_WEBHOOK_SECRET` (`railway variable set KAPSO_WEBHOOK_SECRET --stdin --service backend`), which redeploys the service.
  - Messages sent while it was down are not replayed. Ask the Owner to send them again.
- **Message to the Owner**: "¡Hola! Tuvimos un problemita y no me llegaron tus últimos mensajes 🙏 Ya está resuelto. ¿Me los mandás de nuevo?"

## Gemini 429 or 503

- **Symptom**: the Owner gets "Uy, se me trabó algo. ¿Me lo mandás de nuevo en un ratito?" over and over, or a Post never arrives and they get "Uy, se me trabó algo armando esto. ¿Lo intento de nuevo?".
- **How to check**:
  - Logs: `orchestrator failed for ***1234` or `post <id> failed for ***1234`, with a traceback whose message holds `429` / `RESOURCE_EXHAUSTED` (quota) or `503` / `UNAVAILABLE` (Google overloaded). The `llm agent=...` lines stop showing `status=completed`.
  - Google AI Studio, the project's usage and rate limits: is a per-minute or daily quota used up? Is the key's project still on a billed tier ([#187](https://github.com/guidodinello/build101/issues/187))?
- **Fix**:
  - 503: Google's side. The client already retries 5xx. Wait and try again from a test number.
  - 429 per minute: wait a minute. 429 daily: requests-per-day quotas reset at midnight Pacific time (confirm on [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), not re-read for this runbook). The client doesn't retry 429 on purpose, since a daily-quota 429 once asked to wait 19 h (`app/llm/client.py`). If it keeps happening, check the billing tier and raise the quota in Google Cloud.
  - A key revoked or out of credit shows up as 4xx errors other than 429: replace `GEMINI_API_KEY` on Railway with a key from the billed project.
- **Message to the Owner**: "Estoy con mucha demanda en este momento y me está costando responder 🙈 Dame un ratito y te aviso cuando esté de vuelta."

## Renderer errors (missing or mismatched renderer secret)

- **Symptom**: designed Posts and Carousels fail ("Uy, se me trabó algo armando esto"). Posts made from the Owner's photos as they are still work.
- **How to check**:
  - Logs: `post <id> failed for ***1234`, with `RendererError: renderer answered 401` (the secrets don't match), `renderer answered 503: {"error":"renderer_not_configured"}` (Vercel has no `RENDER_SECRET`), or `renderer unreachable` (wrong `RENDERER_URL`, or Vercel down).
  - Railway: `RENDERER_SECRET` and `RENDERER_URL` are set. Vercel, the frontend project, Settings, Environment Variables: `RENDER_SECRET` is set for Production.
- **Fix**: set the same value in both places, `RENDERER_SECRET` on Railway (backend) and `RENDER_SECRET` on Vercel (frontend), then redeploy the frontend on Vercel so the new value is read. `RENDERER_URL` is the Vercel production domain. Then ask a test number for a design.
- **Message to the Owner**: "Tuve un problema armando el diseño 🙈 Ya lo arreglé. ¿Querés que lo arme de nuevo?"

## A Post stuck in `publish_pending`

- **Symptom**: the Owner was told "Instagram lo está procesando, en un ratito aparece en tu cuenta ⏳", and the Post never showed up on Instagram.
- **How to check**:
  - Logs: `post <id>: publish_pending (...)` and the `post <id> outcome unknown` or `in flight` lines before it. The error in parentheses says what Zernio answered.
  - Zernio dashboard and the Instagram account: did the Post go live, fail, or is it still processing? Every Post goes to the one demo account for now ([ADR 0024](../decisions/0024-mvp-single-demo-instagram-account.md)).
  - Posts live in memory, not in the database ([#181](https://github.com/guidodinello/build101/issues/181)), so the logs and Zernio are the only record. The follow-up for pending Posts is [#202](https://github.com/guidodinello/build101/issues/202).
- **Fix**:
  - Live on Instagram: send the Owner the link.
  - Failed in Zernio: don't publish it again on your own. The Owner asks for it again in the chat and approves the new Post ([ADR 0007](../decisions/0007-approve-every-post.md)).
  - Still processing after about 30 minutes: open a ticket with Zernio, and tell the Owner you're checking.
- **Message to the Owner**:
  - Live: "¡Listo! Ya está publicado en tu Instagram 🎉 <link>"
  - Failed: "Instagram no terminó de subir el post 🙈 ¿Me lo pedís de nuevo así lo subo?"

## A stuck or failed job (including a Business stuck in `generating_brand`)

- **Symptom**: the Owner finished the wizard and never got the summary of their brand, or got "Uy, se me trabó algo armando esto. ¿Lo intento de nuevo?" with a [Reintentar] button.
- **How to check**:
  - Database:

    ```sql
    select b.onboarding_state, j.id, j.kind, j.status, j.attempts, j.error,
           j.retry_offered_at, j.created_at, j.finished_at
    from businesses b join jobs j on j.business_id = b.id
    where b.owner_phone = '<digits>'
    order by j.created_at desc;
    ```

  - `running` for more than 5 minutes: the process that ran it died. The runner gives it back to the queue, or fails it, within a minute.
  - `failed` with `retry_offered_at` set: the Owner already has the [Reintentar] button.
  - `onboarding_state = 'generating_brand'` with the last `generate_brand` job `failed` and no `retry_offered_at`: nothing will run it again until the backend restarts.
  - Logs: `job <id> (<kind>) failed` with its traceback, and `job ... interrupted on attempt ...`.
- **Fix**:
  - With the button: ask the Owner to tap [Reintentar]. It queues the job once.
  - Without it: restart the service (Railway dashboard, the active deployment, Restart). At startup the runner queues a brand job for every Business still in `generating_brand` that has nothing queued or offered ("queued N brand jobs for Businesses stuck generating their brand" in the logs).
  - The same job failing again: read its `error` and look for the cause in the other entries (Gemini, renderer).
- **Message to the Owner**: "Se me trabó algo armando el resumen de tu marca 🙈 Ya lo estoy haciendo de nuevo, en un par de minutos te llega."

## An expired magic link

- **Symptom**: the Owner opens the wizard and sees "Este link venció".
- **How to check**: the link is over 7 days old (`magic_links.expires_at`), or `/api/o/{token}` answered `410 link_expired` in the logs.
- **Fix**: any message the Owner writes in WhatsApp before submitting the form gets a new link (one per 30 seconds). Their saved answers stay on the Business, so the new link picks up where they left off.
- **Message to the Owner**: "Ese link ya venció 🙈 Escribime cualquier cosa por acá y te mando uno nuevo al toque."

## A Post lost after a deploy

- **Symptom**: the Owner taps [Aprobar] or [Publicar ahora] and gets "Ese botón ya no está activo 🙂", or "subilo" finds nothing, a while after the Post arrived. Its image may also fail to load.
- **How to check**: Railway, Deployments: a deploy (or a crash and restart) happened between the Post and the tap. Posts, their images and the Approval context live in memory, so a restart drops them ([backend README § One instance](../../backend/README.md#one-instance); fixed by [#181](https://github.com/guidodinello/build101/issues/181)).
- **Fix**: nothing to recover. The Owner asks for the Post again, which costs a new generation. Avoid it by merging backend changes outside pilot hours ([backend README § When to merge](../../backend/README.md#when-to-merge-backend-changes-during-the-pilot)).
- **Message to the Owner**: "Perdón, hice una actualización y se me perdió el post que te había mandado 🙏 ¿Me lo pedís de nuevo así te lo armo?"

## A failed deploy or pre-deploy migration

- **Symptom**: a merge to `main` didn't change anything in production, or Railway marks the deployment failed. Owners usually notice nothing: the previous deployment keeps serving.
- **How to check**:
  - Railway, Deployments, the failed one: build logs (`railway logs --service backend --build`), then deploy logs.
  - A failed migration shows the Alembic or SQL error in the pre-deploy output.
  - `ENV=prod refuses to start; fix these settings: ...` names each missing or demo setting ([backend README § Environment variables](../../backend/README.md#environment-variables)).
  - `/ready` stuck on 503 names the failed check.
  - `commit` in `/ready` is still the old commit.
- **Fix**:
  - A setting: set it on Railway, which redeploys.
  - A migration: fix it forward in a new PR. A rollback doesn't undo migrations, and a `downgrade` is run by hand only when you know what it drops ([backend README § Rollback](../../backend/README.md#rollback)).
  - A bad build: revert the PR on `main`.
  - If the running deployment itself is broken: redeploy the previous one from the dashboard.
- **Message to the Owner**: none while the previous deployment serves. If Owners were affected, use the message of the matching entry above.
