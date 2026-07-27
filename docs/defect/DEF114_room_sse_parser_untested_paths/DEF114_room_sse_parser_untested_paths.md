# DEF114 — Room SSE parser: `agent_token` unescaping and stream termination are untested

**Filed:** 2026-07-27 (AT:R65) · **Source:** prompt (CR090-MOBILE audit) · **Area:** mobile · **Status:** open

## What's broken

Two shipped code paths in the Room's SSE parser have **no test coverage**, proven by mutation rather
than inferred:

| Mutation | Change | Result |
|---|---|---|
| **M1** | Swap `agent_token`'s unescape order — `.replaceAll(r'\\',r'\')` before `.replaceAll(r'\n','\n')` | suite stayed **green** |
| **M2** | `done` no longer terminates the generator | suite stayed **green** |

Both were run by the CR090-MOBILE auditor against `lane/CR090-MOBILE.coder.mobile` @ `299a6f8`,
each reverted after observation.

## Why it matters

- `agent_token` carries **every analyst's streamed text**. The two `replaceAll` calls are
  order-dependent: unescaping `\\` first would consume the backslash of a `\n` pair, so a wrong order
  corrupts transcript text rather than throwing. Silent corruption, no test, no alarm.
- The `done` case's `return` is **what ends a Room run**. Break it and the stream never terminates —
  the client hangs on a run that has actually finished.

Neither failure is loud. That is the DEF038/DEF063 class again: it would be discovered by a user, not
by the build.

## Not a CR090-MOBILE regression

CR090-MOBILE refactored this switch out of `streamRoom` into `parseRoomSseEvent`, and the auditor
confirmed the moved case bodies are **byte-identical** to `main` (`git show
main:mobile/lib/services/api/api_client.dart`). The lane preserved behaviour and passed audit
correctly. It inherited the gap; it did not create it. This defect exists so the gap survives the
audit file rather than being closed with it.

## Root cause

`ApiClient` constructs its own `http.Client()` inline with **no injection point**, so nothing that
runs through `streamRoom` was unit-testable. That is precisely why CR090-MOBILE had to extract a pure
function to test the new event at all.

## Fix scope

1. **M1 is now cheap** — CR090-MOBILE's `parseRoomSseEvent` is a pure function. Add a test asserting
   `agent_token` unescaping handles `\n`, a literal `\\`, and the `\\n` interaction that makes the
   order matter.
2. **M2 needs a decision** — reaching `streamRoom`'s generator termination requires injecting the
   HTTP client. Either do that, or record explicitly that stream termination is covered only by
   manual/device testing. **Do not** claim coverage that doesn't exist.

## Acceptance

- A mutation swapping the unescape order turns a test **red**.
- Either a mutation breaking `done`'s termination turns a test red, or the decision not to inject is
  recorded with its reasoning in the source.
- No change to the shipped parsing behaviour — this is coverage, not a behaviour fix.
