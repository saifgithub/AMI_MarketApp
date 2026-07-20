# DEF073 — Raw 5xx errors shown to users (add friendly handling)

**Source:** `bug:7f0c5531` · **Reporter:** Platinum Anchor (`8f1e288a`, floor_pass, iOS `0.1.0+39`) · **Filed:** 2026-07-20 (AT:R63) · **Status:** resolved AT:R63 — typed `ServerUnavailableException` + central mapping (SSE + Dio interceptor) + friendly Retry card; ships `0.1.0+41`. Reaction chosen by Saiful: *"Add friendly 5xx handling."*

## Symptom

Report (no screenshot): *"I got an error 502. what happened?"* The user saw a raw
`502`/error with no explanation and had to ask what it meant.

## Context — the root cause is already fixed (DEF070)

The *infra* cause of the 502 is **DEF070** — Cloudflare tunnel QUIC connections flapped,
so while every edge connection was mid-reconnect the CF edge had no route → 502 despite a
healthy backend. Fixed at AT:R63 by forcing HTTP/2 (`TUNNEL_TRANSPORT_PROTOCOL`). The
tunnel recreate that carried that fix happened ~30 min before this cycle; the reporter's
11:33 UTC 502 predates it. **So the 502 itself should now be rare.**

This DEF is the *client-side defensive layer* Saiful asked for on top of DEF070: when a
5xx **does** occur (deploy, restart, transient edge blip), the user should see a friendly
message, not a raw status code.

## Root cause of the bad UX

The client surfaces transport errors raw. `api_client.dart` throws generic exceptions on
non-2xx (e.g. the Room SSE path throws `Exception('HTTP 402 from room stream')` at
`:585`, and Dio 5xx bubbles up as an unmapped `DioException`). There is no
`502/503/504 → friendly, localized message` mapping anywhere in the client. Same raw-error
family as **7eea4eb8** (Room 402 shown raw).

## Fix plan

Add a single 5xx→friendly mapping, applied centrally:

- In `api_client.dart` (or a shared Dio interceptor), catch `502/503/504` and raise a
  typed error the UI renders as e.g. *"AMI's briefly offline — try again in a moment."*
- New localized string (`app_en.arb`, `@`-metadata, AR/MS placeholders).
- Cover both REST and the Room SSE stream path (the SSE path currently only special-cases
  402 → paywall; add a 5xx branch alongside it).
- Consider a one-tap **Retry** affordance on the error card.

Scope: mobile client + l10n. No backend. Pairs naturally with a fix for 7eea4eb8 (same
raw-error surface).

## Out of scope

Any further tunnel/infra hardening beyond DEF070 (that's an infra concern, already
addressed). Automatic silent retry with backoff — a friendly message + manual Retry is the
agreed minimum.
