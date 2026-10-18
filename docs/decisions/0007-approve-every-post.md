# 0007: Every post needs explicit approval

- Date: 2026-10-17
- Status: proposed

## Context

Owners fear losing control of their account and publishing something "not like us". Options were approving each post, approving the weekly plan then auto-publishing, or configurable autonomy.

## Decision

**Each post** is approved with a button tap (or an explicit approval in text that maps to the same handler). The rule is enforced in code: the publisher refuses any post that is not `approved`/`scheduled`, whatever the LLM says.

## Consequences

- Trust and safety by construction; good demo talking point.
- More taps for the owner. A per-business "auto mode" can be added later as a setting without changing the state machine.
- A bare "sí" or "dale" is explicit when it answers the assistant's own question about publishing that post; code detects the question and the yes ([ADR 0028](0028-orchestrator-memory-and-context.md)).
