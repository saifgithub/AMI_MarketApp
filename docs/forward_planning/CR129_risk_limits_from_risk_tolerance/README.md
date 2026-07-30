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

## Preset tables — grounded in the curriculum + published behavioural-finance data

Saiful, 2026-07-30: *"use our lessons as guidance for these numbers. And then search the web for
similar behavioural investments data and let's set it that way."* Both done. **An earlier draft of
this doc claimed the curriculum states no numbers — that was wrong**, the greps were bad. Lesson
**047 Revenge trading** specifies a 60-minute tilt window and a 2-hour cooldown example; **014
Position sizing** teaches 1% risk per trade; **017 Portfolio exposure** works the 5 × 1% = 5%
correlated-cluster example; **018 Drawdown management** uses a 15% mandated ceiling.

| risk | max positions | cooldown | trades/day | trades/week | total open risk | names reachable |
|---|---|---|---|---|---|---|
| 1 | 65 | 4h | 2 | 6 | 25% of drawdown (7.5%) | 50 |
| 2 | 65 | 2h | 3 | 9 | 30% of drawdown (9.0%) | 60 |
| 3 | 35 | 1h | 4 | 12 | 35% of drawdown (10.5%) | 35 |
| 4 | 30 | 1h | 5 | 15 | 45% of drawdown (13.5%) | 30 |
| 5 | 30 | 0.5h | 6 | 20 | 50% of drawdown (15.0%) | 30 |

### Sourcing, per column

1. **Max open positions** — `max(30, names needed to deploy fully at your per-name cap)`.
   The floor of 30 is the evidence: Evans & Archer (1968) put the old rule at 8-10; the modern range
   is ~20-40 with 30-50 the usual "past here it stops helping" band; Raju (2021) needs 40-50 names
   for a 90% cut in idiosyncratic risk. **Never below 30 for any profile** — diversification is not
   what a user trades away for return.
2. **Total open risk** — a fraction of the drawdown *the user stated*, so it is per-user rather than
   a constant. Consistent with lesson 017's teaching that N correlated positions at 1% each carry N%
   of real risk.
3. **Cooldown** — anchored on lesson 047's own 60-minute tilt window, scaled 30min-4h. **No profile
   defaults to zero**: the cortisol/prefrontal response to a loss is universal, not a beginner trait,
   and the cooldown is the cheapest intervention in the literature.
4. **Trade pace** — the strongest evidence of the four. Barber & Odean (66,465 households,
   1991-1996): most-active **11.4%**/yr vs least-active **18.5%**, market 17.9% — before costs both
   groups picked about equally well, so the whole gap was activity. Taiwan (1992-2006): **<1%** of
   day traders reliably profitable, **>80%** losing in a typical half-year, **15%** still active
   after three years. These caps catch a *burst* (lesson 047's tilt spiral), and even risk 5 sits
   far below day-trading frequency **on purpose** — a simulator that permits 50 trades/day trains
   the single most reliably wealth-destroying retail behaviour on record.

### The tension, stated rather than hidden

These limits are **looser than the evidence would justify for real money**. At 75% average annual
turnover the Barber-Odean households were already over-trading, and this table permits well beyond
that. Deliberate: CR101's L3 rationale is that in a simulation-only trainer the blow-up IS the
lesson, and a learner cannot learn from trades they were never allowed to place. Days to accumulate
30 trade outcomes: 35 / 23 / 17.5 / 14 / 10.5 — slow enough to discourage churn, fast enough to
learn. The lesson below carries the rest of the teaching.

### Companion lesson — required, not optional

`content/lessons/365_your_risk_limits_in_ami.en.mdx` — **"Your risk limits, and why they sit where
they do."** Saiful: *"create at least one lesson that explains this all to the user specifically for
Ami trade settings so that the user understands."* Explains all seven limits, why max-positions is
not a risk dial, that open risk is exposure × stop distance (not exposure), and that loosening a
limit the first time it binds is the trap. Carries `sources:` in frontmatter (internal-only
provenance per the BOK rule). **`retranslate:[ar,ms]`** — AR/MS versions owed.

**Content follow-up owed:** lesson 047 currently says the cooldown is *"tracked in the Decision
Journal, not enforced by the app."* CR129 makes that false — it becomes enforced. That line must
change in the same release, and it also carries `retranslate:[ar,ms]`.

## The "Day Trader" preset — Saiful, 2026-07-30

> *"this is a training app. i expect a day trader may also try to learn from using the app, and
> learn the risk. if we do not let them fail in a safe environment, they will fail with real money.
> However, I do also understand the view that the training app should have some basic discipline. I
> suppose since we do allow the customer to change the levels, they do have that facility. I am now
> wondering if we can have a 'day trader' preset, that takes off all the safeguard."*

**Accepted.** It is consistent with CR101's own L3 rationale — in a simulation-only trainer the
blow-up IS the lesson — and it fills a real gap that L2/L3 do not. The capability already exists
(every limit is settable); what does not exist is a **user who can find it**. A day trader today
would have to know to open L2 and loosen seven fields one at a time. A preset makes an intent that
the product should recognise into one tap.

It also fixes a category error in the current design: **a day trader is not "risk 5 but more so."**
The five profiles all implicitly describe swing/position trading at different sizes. Intraday is a
different strategy, not a further point on the same axis, and the five-profile dial cannot express
it at any setting.

### What it must NOT do — the boundary, drawn explicitly

"Takes off all the safeguards" must mean **every user risk limit goes permissive**. It must not
mean the floor is bypassed. `safety_floor.py` already splits `blocked_by` into two families and the
preset touches exactly one of them:

| Family | Reasons | Day-trader preset |
|---|---|---|
| **Not the user's to relax** | `compliance` (Sharia verdict, halal universe, classification), `locale`, `allowlist`, `blocklist` | **untouched** |
| **The user's own risk limits** | `concentration`, `cooldown`, `max_open_positions`, over-trading, open-risk, single-name, drawdown | set permissive |

**No bypass flag.** The deterministic check still runs on every trade; it simply evaluates
permissive numbers. A `skip_floor` boolean would be a second code path that leaks later — precisely
the structural mistake `failure_patterns.md` keeps recording. The floor keeps one path.

### Mechanism — no schema change

The preset writes **explicit permissive overrides** into the seven fields and leaves `risk_score`
alone. It is emphatically **not** `risk_score = 6`: the field is `ge=1, le=5`, feeds `risk_tier_cap`
and appears at 12+ sites in `overlay_generator.py`, and widening it would ripple through all of
them. This rides the machinery CR129 already defines — `None` = follow profile, explicit value =
override — so the preset is a set of writes, nothing new underneath.

Values: sector 100%, single-name 100%, cooldown 0h, open-risk 100%, positions and trade counts set
high. Every one is already a legal value, so the preset is expressible today.

### The part that makes it training rather than just permission

A preset that only removes limits is a faster way to lose with nothing learned. **Instrument it.**
Record when a user switches, then show them their own outcome against the published baselines this
CR is already grounded in: Barber & Odean's most-active cohort at **11.4%**/yr vs least-active
**18.5%**, and the Taiwan day-trading survival curve — **44%** at one year, **24%** at two, **15%**
at three, with under **1%** reliably profitable.

That converts the preset from a permission into an experiment the user runs on themselves, and it
delivers the lesson the way it actually lands — through their own P&L rather than a lesson page.
Without the measurement this is worth building but only half worth having.

### Disclosure

Selecting it must state plainly what it turns off and what the evidence says happens — not to block
(L3: no ceiling, loud disclosure) but because a silent 100% is the thing CR040 exists to stop. The
switch is journalled like any mandate edit, so it is reversible and visible in the Decision Journal.

### Lane impact

Folded into **CR129** rather than filed separately: the machinery is identical (write explicit
overrides through the same resolvers), so a separate lane would duplicate it. Adds to CR129-BE the
preset definition and the switch journalling; adds to CR129-MOBILE the L1 preset entry and its
disclosure. **The outcome instrumentation is a separate follow-up CR** — it needs trade-history
aggregation and a comparison surface, which is real scope and should not ride in behind a settings
change.
