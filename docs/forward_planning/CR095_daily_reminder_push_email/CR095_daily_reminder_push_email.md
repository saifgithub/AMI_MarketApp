# CR095 — Daily challenge reminder (push paid-tier / email free-tier)

**Status:** proposed · **Session:** AT:R65 · **Date:** 2026-07-27
**Source:** CR065 drift item #5, verdict "build it" (Saiful, 2026-07-27).
**Depends on:** CR027 (OneSignal/APNs cert provisioning — Saiful-external, A15) for
the **push** half only. See below — the **email** half is not blocked.

## What

`daily_and_streaks.md` promises a daily challenge reminder at the user's preferred
local time: push for paid tiers, email for free. Neither exists. Push is absent at
every layer (no SDK integration, no `aps-environment` entitlement, no device-token
column — per CR043); there is currently no scheduled outbound-email job either.

## Why

Saiful's verdict: build it. Flagging the asymmetric blocker status below so this
doesn't get stuck waiting on the harder half when the easier half could ship first.

## Important asymmetry — the two halves are NOT equally blocked

- **Push (paid tiers): genuinely blocked.** Requires OneSignal + APNs cert
  provisioning (CR027's A15, Saiful-external) and the push SDK/token-column work
  CR043 already scoped as absent. Cannot start until CR027 clears.
- **Email (free tier): NOT blocked.** `email_service` already ships Resend as the
  primary outbound-mail transport (`RESEND_API_KEY`, live since AT:R32, verified
  end-to-end for magic-link delivery). A daily-reminder email only needs a new
  **scheduled job** (APScheduler, same pattern CR027 proposes for price-alert
  evaluation) that calls the existing sender at each user's preferred local time —
  no new infrastructure.

**Recommendation (confirm at build time):** sequence the email half first —
independent of CR027, ships sooner, and the majority of Floor Pass (free) users are
the ones this reminder is meant to re-engage.

## Scope

**In:** user's preferred reminder time (needs a new column, timezone-aware, mirrors
the pattern used for onboarding-session timezones elsewhere); a scheduled job that
fires the reminder at that local time; email path via existing `email_service`;
push path via OneSignal once CR027 unblocks it.
**Out:** OneSignal/APNs provisioning itself (CR027's scope, not this one).

## Acceptance

- A free-tier user receives a daily reminder email at their configured local time,
  at most once per day, skipped if they already engaged that day.
- A paid-tier user receives the same via push once CR027 clears — email remains as a
  correct fallback for the interim, never a silent no-op.
