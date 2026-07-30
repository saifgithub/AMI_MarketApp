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

   **A real interaction the table must resolve, surfaced before proposing numbers:**
   `max_open_positions` does not scale monotonically with risk the way the others do. It is coupled
   to `single_name_cap_pct` — at risk 1 the per-name cap is **1.5%**, so a conservative user needs
   *many* names to be meaningfully invested (20 × 1.5% = 30%), and a low position cap would lock
   them out of their own portfolio. At risk 5 the per-name cap is 4.5%, so fewer names reach the
   same exposure. Naively giving the "safest" profile the tightest number on every row inverts this
   one and produces a mandate that cannot be satisfied.
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
