# DEF089 — The configured parent-index URL serves an HTML interstitial, not CSV

**Filed:** 2026-07-23 · **Track:** `AT:architect` · **Found by:** track U auditing CR069-BE round 1
**Blocks:** CR069 go-live (`SHARIA_SCREEN_ENABLED=true`) · **Fix lane:** CR069-BE round 2

## What

`sharia_parent_index_url` ([`config.py:171-173`](../../../backend/app/core/config.py), same value at
[`docker-compose.yml:146`](../../../docker-compose.yml)) points at the iShares IVV holdings endpoint.
Fetched by a plain server-side client it returns **HTTP 200 with the iShares product webpage**
(`<!DOCTYPE html>…`), not CSV. Reproduced three times consecutively, and again with a full browser
`User-Agent`/`Accept` pair — no difference.

The response headers are actively misleading: `content-type: text/csv;charset=UTF-8` and
`content-disposition: attachment; filename=IVV_holdings.csv` are both present **on the HTML body**,
consistent with an upstream bot-mitigation layer (`server: istio-envoy`) returning a challenge page
while leaving the origin's download headers in place. A client that trusts the content type gets
HTML.

## Why it matters

CR069's whole three-state promise rests on parent-index membership. SPUS publishes only the
*compliant* set, so without a working S&P 500 constituent source, "screened out" and "never screened"
are indistinguishable — which is design constraint 2, the one that makes this a screen rather than
DEF084 with a bigger allowlist.

**Consequence as configured:** flipping `SHARIA_SCREEN_ENABLED=true` makes
`default_halal_universe()` return a paused (`UNAVAILABLE`, blocking) universe **permanently** — every
`halal`-flagged trade rejected with the honest "screen paused" message, indefinitely rather than
intermittently.

That is constraint 3 working exactly as designed: a real fetch failure fails safe and visible, never
silently. **The code is not at fault.** The configured URL does not serve what CR069 assumed it
would.

## How it survived this long

The CR069 brief's §3 "verified live" research curl'd the **SPUS** URL and reported it in detail —
HTTP 200, 23,574 bytes, 219 tickers, dated. The **parent-index** fetch was never live-tested at any
point in this CR's history, brief or chunk, until this audit round. The lane brief did flag that the
third state needed a source the brief never named ([CR069-BE §1b](../../../orchestration/dispatch/lanes/CR069-BE.assign.md));
what it did not know is that the source chosen to fill that gap does not work.

Worth stating plainly: a "verified live" section that verifies one of two required sources reads as
though it verified both.

## Fix

Folded into **CR069-BE round 2**, alongside the auditor's F2/F3. The auditor correctly scoped this
out of its own verdict — it is not a defect in the code that chunk shipped — but `coder.api` owns
`sharia_universe.py` and is relaunching anyway, and shipping a screen that can only ever pause is not
a finished chunk.

Two candidate shapes, in preference order:

1. **A published mirror fetched the same way HLAL already is** — the CR069 doc's own §3 pattern uses
   a Google-Sheets CSV export for HLAL, which needs no key and no browser emulation. Any S&P 500
   constituent list on a comparable plain-fetch endpoint qualifies.
2. Browser emulation or session handling for the iShares endpoint. **Weaker** — it makes the screen
   depend on defeating a bot-mitigation layer that is free to change without notice, which is a
   silent-breakage source in a feature whose whole point is not to break silently.

Whichever lands, **fetch it live and paste the real response** — that is the check whose absence
caused this.

## Guard

The fetcher tests are fixture-based by design (no network in tests), which is correct and must stay.
So the guard cannot live in the unit suite. It belongs in the terminal `CR069` lane's go-live gate:
**before `SHARIA_SCREEN_ENABLED=true` on any host, both source URLs are fetched live and asserted to
parse.** Acceptance §4's post-promotion smoke would have caught this — but only after a wasted
promotion cycle, and only if someone read the result.
