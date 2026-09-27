# CR245 — Beta infra sizing at 1,000 users

**Status:** proposed
**Filed:** 2026-09-27 (AT:R85)
**Source:** Saiful — "We also sized the cloud setup needed for Beta release," asked to extend
the existing research to a 1,000-user target.

---

## What

Re-runs [CR006](../CR006_beta_infra_cost_research/CR006_beta_infra_cost_research.md)'s cost
model and [CR126](../CR126_beta_infra_provisioning/CR126_beta_infra_provisioning.md)'s
architecture assumptions at **1,000 users** — CR006 topped out at 500 — and corrects one
material error found in CR006's own math along the way (see §2). Research only, no
infrastructure changes. Does not reopen or contradict CR006/CR126/D-066/D-067/D-068; it
extends their numbers one order of magnitude further and flags where the cheap-end
architecture (single scale-to-zero Cloud Run service) starts to strain.

**This sizing is not on the critical path today.** Per
[CR231](../CR231_stabilisation_programme/CR231_stabilisation_programme.md) (2026-09-24), the
GCP/Supabase Beta cutover is explicitly deferred until after the stabilisation programme and
the external TestFlight/Play closed-beta phase — see [CR036 §1](../CR036_go_to_market_plan/CR036_go_to_market_plan.md#1-phase-map--gtm-activity-per-current-gate-re-anchored-on-cr231s-phase-2).
This doc exists so the number is on file and doesn't have to be re-derived when that phase
actually starts.

## Why

Saiful asked for the 1,000-user figure directly. It's also the more realistic target: CR006's
100–500-user range was itself described as "an illustrative usage envelope... sanity-check
against real engagement targets, not a measured fact" (CR006 line 208) — 1,000 users is closer
to what "Beta" as a named phase implies versus Alpha's current internal-only testing.

## Findings

### 1. Compute + DB — cheap-end architecture still holds at 1,000 users

CR126 shipped a **single scale-to-zero Cloud Run service** (`ami-trade-api`,
`concurrency=80`, `timeout=300s`) rather than `hosting.md`'s original 3-service split — a
deliberate cheap-end deviation (D-067). At 1,000 users:

- **B12's own load-test benchmark points are 10/50/100 concurrent streams**
  (`project_plan.md:161`) — nowhere near 1,000 concurrent, because 1,000 *total* users
  doesn't mean 1,000 concurrent sessions. Applying the app's own usage envelope (CR006's 30
  1-on-1 chats + 12 Room sessions/user/month), concurrent load at 1,000 users lands well
  under 100 simultaneous streams for any normal usage distribution — **still inside the
  regime B12 already planned to test**, not a new tier.
- Cloud Run's `concurrency=80` per instance, `max_instances=50` (per `hosting.md`'s sample
  config, not yet revisited under D-067's single-service shape) gives headroom for 4,000
  concurrent requests if instances scale out — 1,000 total users is not going to threaten
  this ceiling under any realistic session-overlap assumption.
- **Supabase**: Free tier's 50K Auth MAU ceiling comfortably covers 1,000 users. The DB-size
  driver is `llm_audit`/`http_audit` volume (CR006's sibling doc,
  `docs/initial_specs/08_tech/data_model.md:20-38`, projects **~5M/~10M rows/month
  respectively at 10K MAU** — scaling those down ~10x for 1,000 users gives **~500K/~1M
  rows/month**, still likely inside Supabase Pro's 8GB DB tier before the explicit monthly
  partitioning `data_model.md` already flags as an MVP-scope follow-up). Supabase Pro's
  $25/mo base (8GB DB, 100K MAU) covers 1,000 users with margin on both DB size and Auth
  MAU; the $0.125/GB overage rate only matters once audit-table retention/partitioning is
  addressed — which is already tracked, not new scope here.
- **Verdict: no architecture change needed for 1,000 users.** The single-service,
  scale-to-zero shape from D-067/CR126 holds. Reopen only if a real B12 load test (still
  pending — B12 hasn't run against live infra) surfaces a surprise, per CR006's own stated
  reopen condition.
- **DEF421** (open, "BETA BLOCKER" — RLS/migration schema drift) still gates any real
  Supabase build regardless of user count; this sizing doesn't change that dependency.

### 2. LLM cost — CR006's per-operation math overcounts Room sessions ~3x

CR006's capstone cost table prices "Room, 3 rounds, premium (180K in/75K out)" per operation.
**The actual code does not run 3 rounds.** `backend/app/services/room_runner.py:6304` hardcodes
`rounds=1` on every `RoomRun`, and the field is only read back for display, never incremented in
a loop (`room_runner.py:5078,5109,5126`). A single Convene the Room run is genuinely **12 agent
calls, one pass** (4 parallel ANALYSTS + 8 sequential ROOM phases — confirmed via the phase
table at `room_runner.py:189-207` and the log line `"Run stopped after {agents_done} of 12
agents"` at `room_runner.py:5204`), not 3x that.

This means CR006's Room-premium cost line — and therefore its Floor Manager LLM-cost verdict
— was priced at roughly 3x the real per-session cost. Correcting for it:

| Item | CR006 (3-round assumption) | Corrected (1-round, actual code) |
|---|---|---|
| Room-premium op, Sonnet 5 intro | $2.78/session | **~$0.93/session** |
| Room-premium op, Sonnet 5 standard (post-2026-09-01) | $4.16/session | **~$1.39/session** |
| Floor Manager LLM/user/mo, Sonnet 5 (12 Room sessions/mo, standard pricing) | $49.95 (Room line alone) | **~$16.65** (Room line alone) |

**This changes CR006's headline verdict materially.** At the corrected 1-round cost, Floor
Manager's Room-session LLM line (~$16.65/mo) plus its 1-on-1/Coach/briefing lines (CR006's
non-Room figures, which don't need correction) lands well under the $34.99 subscription price
— **Sonnet 5 at standard pricing may already be economically viable for Floor Manager**,
reversing CR006's "don't ship Sonnet 5 unconditionally" caution. This is a big enough
correction that it should be independently re-verified (ideally by re-running CR006's own
capstone spreadsheet/artifact with `rounds=1`) before anyone treats it as settled — flagging
it here, not closing the loop unilaterally in a docs-only pass.

Today's date (2026-09-27) is also past CR006's noted **2026-09-01 Sonnet 5 intro→standard
price change** — the $3/$15 per-M-token standard rate is the one that actually applies now,
not the $2/$10 intro rate CR006's other tables lean on by default. The corrected table above
already uses standard pricing.

### 3. All-in cost at 1,000 users (corrected LLM math, Sonnet-5-everywhere)

Extending CR006's blend assumption (60% Floor Pass / 30% Trader / 10% Floor Manager) and its
flat CR007 data-provider overhead (~$115/mo, independent of user count) to 1,000 users, with
the Room-cost correction from §2 applied:

| Users | Path | LLM/mo (corrected) | + Data/infra | **Total/mo** | **$/user/mo** |
|---|---|---|---|---|---|
| 1,000 | Sonnet 5 everywhere, standard pricing | ~2,220 | +115 (+~$30 Cloud Run/Supabase, see §1) | **~2,365** | **~2.37** |
| 1,000 | GLM-5.2 everywhere | ~1,080 | +115 (+~$30) | **~1,225** | **~1.23** |

Method: linear scale of CR006's 500-user Sonnet-5 LLM figure ($3,305/mo) down by the ~3x Room
overcorrection (§2), then doubled 500→1,000 users. This is an arithmetic extension of CR006's
own confirmed unit prices, not a fresh pricing pass — the underlying per-token rates and the
usage envelope (30 1-on-1s + 12 Rooms/user/month) are CR006's, unchanged and un-reverified here.

**This total ($1,225–2,365/mo at 1,000 users) sits inside the profit-sharing agreement's
$750–2,550/mo Beta estimate reference band** (`CR126` line 30-32, itself citing CR006's
pre-correction range) — the corrected, lower LLM cost only makes this more comfortable, not
less. The $600/mo dedicated infra allocation (compute+DB only, excluding LLM) still holds
regardless of which LLM path is picked, since compute+DB cost (~$30/mo at this scale, per §1)
is a small fraction of it.

### 4. What this doesn't change

- **D-066/D-067** (Cloud Run + Supabase, single scale-to-zero service) — confirmed still
  right at this scale, not reopened.
- **D-068** (B7 LLM provider left open) — stays open. The §2 correction makes Sonnet 5 look
  more viable than CR006 concluded, but that's a reason to revisit the decision with better
  numbers, not to make it here. GLM-5.2's Entity List sign-off question (CR006) is unchanged
  either way.
- **CR231's deferral of the whole GCP/Supabase move** — unaffected. This is a sizing
  reference for whenever that phase starts, not a signal to start it now.
- **DEF421** — still blocks any real Supabase migration regardless of these numbers.

## Scope

**In scope:** arithmetic extension of CR006's confirmed unit prices and usage envelope to
1,000 users; the `rounds=1` correction to CR006's Room-operation cost line (a real code fact,
independently verified against `room_runner.py`); compute/DB headroom check against B12's
planned load-test tiers.

**Out of scope:**
- Re-running CR006's live pricing research (Sonnet 5 rates, GLM-5.2 availability, etc.) —
  this doc reuses CR006's confirmed figures as of 2026-07-09, itself already flagged there as
  needing re-verification "close to the actual purchase decision."
- Actually running B12's load test against live infra — still pending, still needs Saiful's
  go-ahead per CR126.
- Deciding B7 (LLM provider) — stays open per D-068, this doc only supplies better numbers
  for whenever that decision gets made.
- Resolving DEF421 — tracked separately, unaffected by user-count sizing.
- Any Terraform/infra changes — CR126's scaffolding is unchanged.

## Acceptance

- [x] CR006's cost model extended to 1,000 users using its own confirmed unit prices.
- [x] `rounds=1` vs. CR006's "3 rounds" assumption verified against `room_runner.py` and
      corrected.
- [x] Compute/DB headroom at 1,000 users checked against B12's planned load-test tiers.
- [ ] Independent re-verification of the §2 Room-cost correction (ideally against CR006's
      original artifact/spreadsheet) before treating the reversed Sonnet-5-viability finding
      as settled — flagged, not closed, in this pass.
- [ ] Saiful reviews the corrected Floor Manager economics (§2) and decides whether it changes
      anything about the B7 timeline or the GLM-5.2 sign-off question.
