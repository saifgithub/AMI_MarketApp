# CR129 — derive all seven risk limits from the 1–5 risk tolerance, and backfill alpha

**Filed:** 2026-07-30 (AT:R65) · **Origin:** Saiful, directly, after asking whether onboarding sets
the new CR101 limits.

## What Saiful asked for

> *"The onboarding questions we already have is enough to determine the users risk tolerance. And we
> have it between 1-5. We would should then set all these risk limits based on these risk tolerance.
> And since we are still in alpha, we backfill them all based on the current risk tolerance scores."*

Two instructions: **no new onboarding questions** — `risk_score` already carries the signal — and
**backfill every existing user** from the score they already have.

## Measured state that makes this necessary

CR101 shipped all seven limits as settable and enforced. **Onboarding sets none of them.** Verified:
zero references to any of the seven in `concierge_engine.py`, `api/auth.py`, or `api/onboarding.py`;
`session_to_mandate_dict()` writes only `risk_score`, `max_drawdown_pct`, `compliance` and the three
`risk_components`. A user completing the interview today gets:

| | Enforced today |
|---|---|
| sector cap | 40% (preset via `concentration_tolerance`) |
| single-name cap | **3.0% in the Room, 50.0% on the trade ticket** |
| max drawdown | 30% |
| post-loss cooldown | **OFF** |
| max open positions | **OFF** |
| max trades / day | **OFF** |
| max trades / week | **OFF** |
| total open risk | **OFF** |

Live Alpha population: **13 current mandates** — risk_score 1×1, 2×4, 3×7, 5×1 (no 4s).

Consequences this closes:

1. **The phantom-mandate gap is only half-closed.** ~6 lessons (DEF102) and ~26 daily challenges
   (DEF117) teach these limits as things the mandate enforces. CR101 made the fields exist; it did
   not put a value in anybody's mandate. The lesson is still false for every user.
2. **DEF187 affects 100% of users, not an edge case.** Because nothing sets `single_name_cap_pct`,
   *every* account has the ~16.7x split — the PM narrates 3% while the trade ticket accepts 45%.

## The decision this CR carries — read before building

**CR101-BE1 deliberately refused to unify the single-name cap**, because making the floor's
trade-ticket fallback follow the risk-tier preset tightened every existing user's cap ~16.7x and
turned 43 tests red. The builder stopped and disclosed; the auditor agreed; I minted **DEF187**
rather than let it be decided inside a coder lane.

**Saiful's directive now authorises exactly that change.** "Set all these risk limits based on
risk tolerance" plus "we are still in alpha, backfill them all" is an explicit, informed decision to
constrain existing users. That is a legitimate product call at 13 mandates — it would not be at
13,000 — and it is what lifts the DEF187 blocker. **This CR therefore closes DEF187 by decision,
not by a new measurement.** Say so in the commit; do not present it as a bug that was discovered.

## Design — ruled here so no lane has to guess

1. **Coalesce-at-read, not a data migration.** `None` on any of the seven means **"follow my risk
   profile"** and resolves through one function per field, keyed on `risk_score`. This is BE1's
   established `resolved_*` pattern. It makes the backfill structural rather than a one-off UPDATE:
   every existing mandate is covered the instant it deploys, and a user who later moves their
   profile has every limit move with it. No migration to write, none to get wrong.
2. **This inverts CR101-BE2's acceptance 4** (`None` meant off / non-binding, so nobody was silently
   constrained on deploy). That inversion is the *point* of this CR and is authorised above. The new
   acceptance is its mirror: prove every user's limits DO change, to the right values for their
   score.
3. **"Off" stays expressible** — CR101's amendment ("they should be able to set whatever they like")
   still binds. No new representation is needed: every one of the seven has a natural off value that
   is already a legal number — cooldown `0` hours, percentages `100`, counts set high. L3's
   loud-disclosure machinery already covers a looser-than-profile value, so choosing off discloses
   itself through a path that exists.
4. **Preset numbers — CORRECTED 2026-07-30, my first wording was wrong.** This originally said
   "derive the 1–5 tables from what the teaching material actually says." **Measured against the
   1,026 files in `content/lessons` and `content/daily_challenges`: the concepts are taught but no
   number is.** "cooling" appears in 6 files, over-trading in 3, "position limit" in 1, and none of
   them states a threshold. So there is nothing to derive from, and a lane following that
   instruction would be silently inventing the numbers instead — which is worse than inventing them
   openly, because the invention would arrive wearing a citation. **The tables are a product
   decision and belong to Saiful**, proposed by the Architect with reasoning and confirmed before
   any lane builds them. Once fixed, the curriculum should be updated to cite the real numbers
   (a content follow-up), which reverses the intended dependency: the mandate becomes the source of
   truth and the lessons are made true against it.

   **`max_open_positions` is NOT a risk-appetite parameter — ruled by Saiful, 2026-07-30.** The
   Architect's first derivation set it to `60% / per-name-cap`, which made position count a function
   of the risk dial and quietly encoded *"aggressive ⇒ holds fewer names."* Saiful rejected the
   premise: *"I understand if I am a low risk tolerance person, I should diversify my holdings, but
   it does not mean if I am a high risk tolerance person I should not. I should still diversify my
   holdings, just that I may trade in riskier investments."* Correct, and the error was worse than a
   wrong number — a **ceiling** of 13 does not *permit* concentration, it **forces** it. No risk
   profile should compel a user to be concentrated, and the per-name cap already does the
   risk-scaling work (at risk 5 you *may* size 4.5% into one name; nothing should require it).

   **Replacement rule — two forces, neither of them risk appetite:**
   `max_open_positions = max(DIVERSIFICATION_FLOOR, names needed to deploy fully at your own
   per-name cap)`, with `DIVERSIFICATION_FLOOR = 30`. It still declines across the profiles, but
   only because a larger per-name cap mechanically needs fewer names to deploy the same capital —
   never because an aggressive user should hold less. A flat value fails for the mirror reason:
   30 names × 1.5% caps a risk-1 user at **45% deployable**, so they could not fully invest.

   **Guard this rule with a test, not a comment:** for every risk score, the number of names a user
   can actually reach — after the open-risk cap is also applied — must be **≥ 30**. That is the
   "nobody is forced to concentrate" invariant, and it is the one a future tweak to any of the three
   coupled numbers could silently break.
5. **The backfill must be loud (CR040).** 13 real users acquire limits they never set. At minimum a
   `MANDATE_EDIT` journal entry per user describing what changed and why; ideally a one-time in-app
   notice. A user hitting a cooldown block they never configured, with no explanation, is the
   failure this project keeps filing defects about.

## Lanes

- **CR129-BE** (`coder.api`, GATE independent) — the five preset tables, the resolvers, unifying the
  single-name cap across both paths (closing DEF187), the journal disclosure, and the inverted
  migration proof.
- **CR129-MOBILE** (`coder.mobile`, GATE independent, DEPENDS-ON CR129-BE) — all seven fields render
  "Following your risk profile" with **the resolved number**, not just the two that do today. Needs
  **DEF193** (mandate GET must expose resolved values) resolved first or bundled.

## Related

**CR101** (built the fields), **DEF187** (closed by this CR's decision), **DEF193** (blocks the
mobile half), **DEF102** / **DEF117** (the curriculum this makes true), **CR040**, **CR046**.

## Proposed preset tables — awaiting Saiful's confirmation

Derived from the anchors that exist, not invented. `max_drawdown_pct` shown at its default of 30;
the open-risk column is **per-user**, computed from the drawdown the user themselves stated.

| risk | max open positions | post-loss cooldown | trades/day | trades/week | total open risk |
|---|---|---|---|---|---|
| 1 | 65 | 2h | 10 | 40 | 25% of drawdown (7.5%) |
| 2 | 65 | 1h | 15 | 60 | 30% of drawdown (9.0%) |
| 3 | 35 | 1h | 20 | 80 | 35% of drawdown (10.5%) |
| 4 | 30 | 0.5h | 30 | 120 | 45% of drawdown (13.5%) |
| 5 | 30 | 0h | 50 | 200 | 50% of drawdown (15.0%) |

Rules behind each column:

1. **Max open positions** — `max(30, names needed to deploy fully at your per-name cap)`. Declines
   only because a bigger per-name cap needs fewer names. Never forces concentration (see above).
2. **Total open risk** — a fraction of the drawdown *the user said they could stomach*, so a
   simultaneous stop-cascade costs part of that budget rather than all of it. The only one of the
   five with a genuine user-stated anchor.
3. **Post-loss cooldown** — interrupts a tilt sequence inside one session. **The clock is real
   wall-clock** (`last_loss_closed_at + timedelta(hours=…)`), so an aggressive number locks a user
   out of a *learning app* for real days. An earlier draft proposed 48h at risk 1; that was wrong.
4. **Trade pace** — catches bursts, never throttles deliberate practice. Sanity metric: days to
   accumulate 30 trade outcomes — 5.2 at risk 1 down to 1.1 at risk 5. An earlier draft's 3/week
   meant **10 weeks** for a beginner to see 30 outcomes, which inverts the product's purpose.

**Binding order at a 10% stop** (measured): open-risk binds first for risk 1–2, position count for
risk 3–5. Names actually reachable after both apply: 50 / 60 / 35 / 30 / 30 — all ≥ the
diversification floor.

**Calibration stance, stated so it is not mistaken for sloppiness:** these are deliberately looser
than a real-money risk framework. CR101's own L3 rationale governs — *in a simulation-only trainer
the blow-up IS the lesson*. These limits are teaching instruments that should bite when a user is
genuinely over-extended and stay out of the way otherwise; a limit that fires constantly trains
users to resent it, and one that never fires teaches nothing.
