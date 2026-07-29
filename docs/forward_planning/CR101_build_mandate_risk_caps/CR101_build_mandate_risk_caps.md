# CR101 — Build the Mandate risk caps the curriculum already teaches

**Filed:** 2026-07-27 · **Status:** proposed · **Decision:** Saiful, 2026-07-27 — *"create a CR for the caps. It will be build."*
**Amended:** 2026-07-29 (AT:R59, room-quality) — Saiful, verbatim: **"All risk parameters must be disclosed and user-settable."** Read Amendment 1 first; it adds a governing principle, an audit of what exists today, one blocker that must land first, and a schema decision the original scope left open.
**Amended again:** 2026-07-29 (AT:R65, architect review at Saiful's request) — Amendment 2 corrects one factual claim in Amendment 1 that would have caused a silent behaviour change if built as written, and adds two build-blocking gaps. **Read Amendment 2 before acting on Amendment 1's scope item 10.**
**Amendment 3:** 2026-07-29 (AT:R65) — Saiful's decisions on the three questions Amendment 2 left open. AT:R59 has closed; **track R is the sole architect and owns this CR.** Amendment 3 **supersedes** Amendment 2's recommendations where they differ, and supersedes scope item 10.
**Amendment 4:** 2026-07-29 (AT:R65) — reconciles Decision 3's preset spine against the curriculum, as Amendment 3 required. Saiful approved the spine and the lesson agrees with it; the field is renamed to the curriculum's own `min_risk_reward_ratio`; and it turns out **the cap is already a phantom-mandate field taught by two lessons in three languages**, which moves it from "a job invented for `regret_asymmetry`" into the DEF102/DEF117 cohort this CR exists to close. Carries the no-levels recommendation, awaiting Saiful. **Amendments 3 + 4 together are the current statement of scope — read them last and treat them as binding.**

---

## Amendment 2 (2026-07-29, AT:R65) — review findings

Reviewed at Saiful's request. Amendment 1's four load-bearing facts were re-verified
independently against `main` and **all four hold**: `_TOLERANCE_TO_CAP` = 25/30/40/50/60
(`sector_allocation.py:52-58`), `DEFAULT_RISK_TIER_CAPS = {1:1.5, 2:1.5, 3:3.0, 4:4.5, 5:4.5}`
(`trading_math/sizing.py:22`), `SINGLE_NAME_ABSOLUTE_CAP_PCT = 50.0` (`sizing.py:26`), and the
shallow merge with its `compliance`-only special case (`mandate_store.py:91-113`). The blocker
diagnosis and its sequencing are correct. What follows is what the review changes.

### Correction — `drawdown_response` and `regret_asymmetry` are NOT dead (blocks scope item 10)

Amendment 1 states they are *"consumed by **nothing**"* and recommends deleting both. **That is
wrong.** Both are read by `_derive_risk_score` (`concierge_engine.py:429-435`):

```python
def _derive_risk_score(session: OnboardingSession) -> int:
    rc = session.risk_components_partial
    a = rc.get("drawdown_response", 3)
    asym = rc.get("regret_asymmetry", 0)
    c = rc.get("concentration_tolerance", 3)
    base = round((a + c) / 2)
    return max(1, min(5, base + asym))
```

`risk_score` selects the enforced single-name cap via `risk_tier_cap`. So both fields **do**
influence an enforced limit — once, at onboarding. Amendment 1's grep missed it because it
classified `concierge_engine` wholesale as "a constructor that defaults them"; this call site is
in that same module but is a *consumer*, not a default.

Consequence: **deleting them silently changes how every new user's risk tier is derived**, and
with it their single-name cap. That is a behaviour change disguised as a cleanup.

The accurate characterisation is that they are **onboarding interview inputs, not mandate state** —
written once, consumed once to derive `risk_score`, then inert. Under the Amendment 1 invariant
they fail (b), (c) and (d) *as Mandate fields*, which is a reason to move them off the Mandate (the
Mandate is the enforcement instrument), not to delete the inputs. **Recommended resolution:** keep
the two interview questions and the derivation, relocate the values to the onboarding session
record, and drop them from `Mandate`. The user's post-onboarding control over the result is the
`risk_score` slider, which already satisfies (d).

### Gap 1 — the rename breaks BL5 rollback (build-blocking, affects scope item 8)

`get_version` does `Mandate.model_validate(row.snapshot)` (`mandate_store.py:149`) — historical
versions are stored as raw JSON (`snapshot=updated.model_dump(mode="json")`, `:85`) and parsed
through the **current** schema on every read. Renaming `concentration_tolerance` to a required
`sector_cap_pct` therefore makes **every pre-migration version unparseable**, so `get_version`,
`list_versions` and `rollback_to` start raising `ValidationError` for any user with history.

This is load-bearing precisely because Amendment 1 cites rollback as the reason this CR does not
need to rebuild auditing ("every risk change is therefore already auditable and revertable"). The
migration in item 8 must **rewrite historical snapshots**, not just current rows — or the schema
must carry a deserialisation alias for the old key. Add a test that rolls back to a snapshot
written under the old schema.

### Gap 2 — the invariant guard must derive its field set, not hard-code it

Amended Acceptance asks for "one guard [that] enumerates every Mandate field that feeds an enforced
limit." If that enumeration is a literal list inside the test, the guard has the **same drift
failure it exists to prevent**: field 8 gets added, nobody updates the list, and the guard passes
while the field is undisclosed. Derive the set from the schema instead — mark enforced fields
declaratively (e.g. `Field(json_schema_extra={"enforced": True})`) and have the guard iterate
`Mandate.model_fields` — so a new field is inside the guard by construction. Per the house rule the
`failure_patterns.md` entry should name the *derived* check, not the list.

### Three smaller findings

1. **Shown-equals-enforced has a second path (sharpen item 9).** Item 8 demotes
   `DEFAULT_RISK_TIER_CAPS` to a preset, but PM sizing calls `risk_tier_cap(risk_score)` directly.
   If a user sets 35% and the PM still clamps to 4.5% off the tier table, shown ≠ enforced and
   CR046 is violated at the only place it matters. Item 9 must state explicitly that the sizing
   path reads the **stored** cap.
2. **The sector cap silently does not fire when its context degrades.**
   `_build_room_sector_context` (`room_runner.py:729-747`) returns empties on **any** exception, so
   `allocate_by_sector` never runs and check 6b cannot fire. Defensible today as a
   don't-block-on-outage guard. Once the cap is a number the user chose and was shown, a silent
   non-application is exactly the failure CR040 exists to stop — the run must disclose that the cap
   could not be evaluated.
3. **The time-based caps are undefined.** `max_trades_per_day` / `max_trades_per_week` need a
   stated basis: whose day (UTC or the user's timezone), and rolling-window or calendar. Settle it
   here rather than in the lane.

### Design position on item 9

Amendment 1 proposes making `SINGLE_NAME_ABSOLUTE_CAP_PCT` user-settable. Agreed, and it should go
further: once the user's own cap is enforced, a second 50% backstop they cannot change **is** the
thing Saiful's rule removes. Keep one enforced number — theirs. The floor loses no power; it
enforces what the user set. If a backstop survives it needs a stated reason that is not its name.

### Interaction with DEF110 (fixed + promoted 2026-07-29, `alpha-2026-07-29-3`)

Two of this CR's proposed caps — `max_open_positions` and `total_open_risk_pct` — read the same
`sim_holdings` the sector cap reads. Until DEF110 was fixed that table carried phantom shares from
self-closed positions (measured: 101 phantom shares across 3 accounts; one account read Technology
75% against its 40% cap when it held no Technology at all). Those caps would have been built on
corrupted input. The inputs are correct now, but the episode is the strongest available argument
for Layer 3's loud disclosure: **that breach was enforced and invisible for weeks.**

### Scope observation

13 scope items and 10 acceptance criteria is large for one CR, and item 7 (nested merge) is a
small, independently-shippable fix that everything else waits on. Suggest landing item 7 alone
first, then schema + enforcement, then UI.

---

## Amendment 3 (2026-07-29, AT:R65) — Saiful's decisions on the three open questions

AT:R59 closed; track R is now the sole architect and owns this CR. The three questions Amendment 2
left open were put to Saiful and decided. **These decisions supersede Amendment 2's recommendations
where they differ** — Amendment 2 recommended moving the two fields off the Mandate and deleting the
50% backstop; Saiful chose to wire and to keep, respectively.

### Decision 1 — wire `drawdown_response` and `regret_asymmetry` to real behaviour

Chosen over "move off the Mandate" and over "delete". Both fields stay, and each gets a named
enforced consumer:

| Field | Becomes | Enforced by |
|---|---|---|
| `drawdown_response` 1–5 | `cooldown_after_stop_minutes` | new floor check: block a new buy inside the cooldown window after a stop-out |
| `regret_asymmetry` −1…1 | `min_reward_risk_ratio` | new floor check: block a setup whose computed R:R is below the user's minimum |

**This composes with item 8 rather than fighting it.** Item 8 says *store the limit, not the
ordinal*. Applied to all three `risk_components` at once, the ordinals become explicit limits:

```
concentration_tolerance 1-5  ->  sector_cap_pct
drawdown_response       1-5  ->  cooldown_after_stop_minutes
regret_asymmetry       -1..1 ->  min_reward_risk_ratio
```

The onboarding classifiers keep their questions and become **preset selectors** that write the
initial explicit values, exactly as `_TOLERANCE_TO_CAP` is demoted to a preset table.

**Consequence worth noting: `RiskComponents` may dissolve entirely.** If all three members become
flat explicit limits on `Mandate`, the nested object has no remaining members, and the shallow-merge
422 (Amendment 1 finding 4 / item 7) stops applying *to these fields*. **Item 7 still lands** —
`compliance` is still nested and carries its own hand-written special case, and any future nested
group needs the same treatment — but its urgency as a blocker for items 5/8 drops. Confirm the
member list is empty before removing the class; do not remove it speculatively.

`_derive_risk_score` (`concierge_engine.py:429-435`) must be reworked either way, because it reads
`concentration_tolerance`, which item 8 removes.

### Decision 2 — keep `SINGLE_NAME_ABSOLUTE_CAP_PCT`, and make it user-settable

Chosen over removing it. This resolves Amendment 1 finding 3 ("two single-name caps ~11× apart, and
item 3 does not say which binds") **by making the two roles explicit rather than collapsing them**.
They are not duplicates; they are a *target* and a *hard limit*:

| Number | Role | Who applies it | Today |
|---|---|---|---|
| `single_name_target_pct` | what the PM **sizes to** | `risk_tier_cap` in PM sizing | 1.5–4.5% by tier |
| `single_name_limit_pct` | what the floor **blocks at** | `check_mandate_compliance` check 6 | flat 50%, unchangeable |

Both become explicit, disclosed and user-settable. **Add a cross-field validation: target ≤ limit**,
rejected loudly at `PATCH` time rather than silently clamped. The settings UI must state each
number's job in one line, or it ships the confusion Amendment 1 flagged — "we size to this / we
refuse above this".

This also sharpens Amendment 2's smaller finding 1: PM sizing must read the stored
`single_name_target_pct`, not `DEFAULT_RISK_TIER_CAPS`, or shown ≠ enforced.

### Decision 3 — `regret_asymmetry` controls the minimum reward:risk ratio

Chosen over overlay-context-only and over dropping the field. The point of this option is that
**nothing is invented** — every piece already exists and was verified on `main` (2026-07-29):

- `trading_math/trade.py::risk_reward(entry, stop, target)` computes it, `(target−entry)/(entry−stop)`
- `room_runner.py:955` and `:1019` already call it at verdict time
- it is a CR046 metric (M06) and is already drawn on the CR106 Verdict Board ribbon as `2.8 : 1`
- lesson `016_risk_reward_ratio` already teaches it

Semantics: a loss-averse user (`+1`) demands a fatter payoff before risking capital; a
fear-of-missing-out user (`−1`) accepts thinner setups. Suggested preset spine, to be confirmed
against lesson 016's own numbers so the curriculum and the product agree: `−1 → 1.0`, `0 → 1.5`,
`+1 → 2.5`.

**Blocker for this check — the floor cannot currently see the levels.** `ProposedTrade`
(`schemas/trade.py:61-78`) carries `ticker`, `side`, `quantity`, `order_type`, `limit_price` and
**no entry / stop / target**, so `check_mandate_compliance` has nothing to compute R:R from, even
though `SimEngine.submit` accepts `stop=` and `target=` at the call site and drops them before
building the `ProposedTrade`. Two routes, and this CR must pick one:

1. **Add `stop` / `target` to `ProposedTrade`** and thread them from `SimEngine.submit`. Keeps every
   floor check in one place, which is the CR038 "make it structural" argument. Touches the shared
   schema.
2. **Enforce at the verdict layer** in `room_runner`, where `risk_reward` is already computed. Less
   plumbing, but splits mandate enforcement across two modules — the DEF098 failure class (two
   renderers of one rule, neither a superset). **Not recommended.**

Route 1 is recommended.

**Decide the no-levels case explicitly, do not let it be discovered.** A market order with no stop
has no R:R by construction. A user who has set a 2.5:1 minimum and then trades with no stop has
escaped their own mandate through a hole. State the rule in the build: either such a trade is
refused with a named reason, or the minimum only binds when levels are present — and if the latter,
the overlay and the UI must say so. Silently skipping the check is the CR040 failure.

### Amended Scope — supersedes item 10, adds items 14–16

10. ~~Wire or delete `drawdown_response` and `regret_asymmetry`~~ → **WIRE both**, per Decision 1:
    `drawdown_response` → `cooldown_after_stop_minutes`, `regret_asymmetry` →
    `min_reward_risk_ratio`, both stored as explicit limits under item 8's rule, both enforced by a
    deterministic floor check, both in the overlay, both settable.
14. **Two named single-name numbers** (Decision 2) — `single_name_target_pct` (PM sizes to) and
    `single_name_limit_pct` (floor blocks at), both settable, with a `target ≤ limit` cross-field
    validation and a one-line role statement each in the UI. Supersedes the open question in item 9.
15. **Carry the levels into the floor** (Decision 3 blocker) — add `stop` / `target` to
    `ProposedTrade` and thread them from `SimEngine.submit`, so the R:R check lives with every other
    mandate check. State the no-levels rule.
16. **Rework `_derive_risk_score`** — it reads `concentration_tolerance`, which item 8 removes.
    Onboarding classifiers become preset selectors writing explicit limits.

### Amendment 4 (2026-07-29, AT:R65) — the R:R cap is already in the curriculum

Reconciling Decision 3's preset spine against lesson `016_risk_reward_ratio`, as Amendment 3
required, turned up three things that change the item rather than confirm it.

**1. Saiful approved the spine, and the lesson agrees with it.** Lesson 016 states 1.5 twice —
the falsification rule (*"if the chart's natural target is closer than 1.5× the stop distance,
the setup fails the filter before you even price it"*) and the practice task. That is exactly the
midpoint, so **`−1 → 1.0`, `0 → 1.5`, `+1 → 2.5` stands**, confirmed against the curriculum rather
than asserted.

**2. Use the curriculum's field name: `min_risk_reward_ratio`.** Not the `min_reward_risk_ratio`
Amendment 3 coined. The lessons already name it, and it matches the existing
`trading_math/trade.py::risk_reward`. (Both compute reward ÷ risk despite the word order — that is
the conventional reading of the phrase "risk/reward ratio", and the lesson's own worked example
confirms it: `15 ÷ 5 = 3.0`.)

**3. This cap is ALREADY a phantom-mandate field — it belongs to the DEF102/DEF117 cohort this CR
was created for.** It is not a new dial being invented to give `regret_asymmetry` a job; it is a
promise the curriculum already makes and the product does not keep. Measured on `main`:

| Lesson | Languages | What it tells the user |
|---|---|---|
| `016_risk_reward_ratio` | en / ar / ms | *"set `min_risk_reward_ratio` to 1.5 … the PM safety floor will **refuse the ticket**"* |
| `106_asymmetric_rr_in_regimes` | en / ar / ms | sets it to 2.0, and teaches per-regime thresholds — 2:1 trending, 1.5:1–2:1 ranging |

Six files. Lesson 016 also specifies the **enforcement behaviour** — the floor refuses — which
settles by itself the part of Decision 3 that was open, and confirms the "refuse" reading below.
Lesson 106 implies the user re-tunes the threshold by market regime, which the Layer 2 dial
satisfies; it does NOT require a per-regime schema field, and should not be read as asking for one.

**Consequence for content:** once this ships, both lessons flip from wrong-vs-product to correct
with **no text change**, so no AR/MS re-translation is triggered. Add them to the cohort that gets
re-verified green under the original filing's "Consequences for content" section.

### The no-levels ruling — recommendation, awaiting Saiful

Amendment 3 flagged that a market order with no stop has no computable R:R, and that a user who set
a 2.5:1 minimum and then traded without a stop would escape their own mandate. Recommended
resolution:

**Refuse, and make "none" a real setting.** A trade with no stop does not *pass* the check, it is
**unevaluable** — risk is undefined, so it cannot demonstrate 1.5:1. Treating unevaluable as passing
is the DEF059 pattern (proceeding confidently on absent data) and is exactly the bypass shape. The
escape valve is the dial itself: `0` = no minimum, a legal, disclosed, user-chosen setting under
Layer 3. The user can switch it off deliberately but cannot bypass it by accident — which is the
distinction the whole CR rests on. The refusal must name both exits: *"add a stop and target, or
set your minimum to none."*

**Migration guard, and it is not optional.** Migrate every existing user to `0`. If the preset
shipped at 1.5 by default, every stop-less market order in the app would start being refused by a
rule the user never set — which is precisely how DEF149 happened the same day (*"when 1 buy for the
1st time, I am immediately violating the allocation"*). Only onboarding, or the user opening the
dial, should produce a positive value.

**Scope note:** the Room path always carries entry/stop/target, so this hole exists only on the
manual trade ticket. Enforcing on Room verdicts is free.

### Amended Acceptance — adds to the previous ten

- A stop-out starts the cooldown, and a buy inside the window is blocked with a named reason;
  outside it, allowed. Cooldown 0 disables the check.
- A setup below the user's `min_reward_risk_ratio` is blocked with a named reason, and the number
  the floor used equals the one the Verdict Board renders — the same `risk_reward` call, asserted
  against one computation, not two.
- The no-levels case behaves as the CR states, tested both ways.
- `PATCH` with `single_name_target_pct > single_name_limit_pct` is refused with a readable message,
  not clamped.
- PM sizing reads the stored target, proven by setting it to a non-preset value (e.g. 7.3%) and
  reading the size the PM actually proposes.
- Preset spine for `min_reward_risk_ratio` agrees with lesson `016_risk_reward_ratio`.

---

## Amendment 1 (2026-07-29) — every risk parameter disclosed and user-settable

### The principle, and where it comes from

Saiful, on finding that `concentration_tolerance` (which sets the enforced sector cap) cannot be
changed by the user after onboarding:

> *"A risk setting that a user cannot change violates the user's rights. They should be able to
> set whatever they like."* → **"All risk parameters must be disclosed and user-settable."**

This is consistent with the product's own frame rather than an exception to it. The user is the
CEO; the mandate is **the user's instrument**; the safety floor's job is to enforce the user's
mandate **against the agents**. "Uncoachable" (CLAUDE.md, Brief Your Agent) means an agent cannot
argue its way past the mandate — it has never meant the user cannot set it. The floor keeps all of
its power under this rule, because it enforces whatever the user chose.

**The rule this CR now has to satisfy, stated as a testable invariant:**

> A field stored on the Mandate that influences an enforced limit is **(a)** enforced, **(b)**
> disclosed to the user in its own units, **(c)** disclosed to the agents in the overlay, and
> **(d)** settable by the user. Anything that cannot satisfy all four is **deleted**, not hidden.
> There is no third state.

That invariant is what makes this an acceptance criterion instead of a slogan — see Amended
Acceptance below.

### Audit of every risk dial as it stands today (measured 2026-07-29 against `main`)

| Dial | Range | What it actually enforces | Disclosed? | Settable? |
|---|---|---|---|---|
| `risk_score` | 1–5 | PM single-name size clamp via `risk_tier_cap` — `DEFAULT_RISK_TIER_CAPS = {1: 1.5, 2: 1.5, 3: 3.0, 4: 4.5, 5: 4.5}` (`trading_math/sizing.py:22`) | as an abstract 1–5, not as a % | ✅ slider |
| `max_drawdown_pct` | `Literal[10,20,30,50,100]` | floor check 7 (drawdown projection) | ✅ in its own units | ✅ slider |
| `compliance.*` | flags / lists | floor checks 1–5 | ✅ | ✅ toggles |
| `risk_components.concentration_tolerance` | 1–5 | **sector cap** 25/30/40/50/60% (`_TOLERANCE_TO_CAP`, `sector_allocation.py:52-58`), floor check 6b | the *resulting %* is shown on the allocation donut (`api/portfolio.py:76` → `max_allowed`); the setting is not | ❌ **never, after onboarding** |
| `risk_components.drawdown_response` | 1–5 | **nothing** | echoed in the mandate readback only | ❌ |
| `risk_components.regret_asymmetry` | −1…1 | **nothing** | echoed in the mandate readback only | ❌ |
| `SINGLE_NAME_ABSOLUTE_CAP_PCT` | `50.0` | floor check 6 | stated in the PM prompt | ❌ global constant |

Four findings fall out of that table, and each one changes the original scope.

**1. `concentration_tolerance` is written exactly once and is then immutable for the life of the
account.** The only write path is `_classify_concentration` (`concierge_engine.py:358`) during the
onboarding interview — a keyword match on free text (`"60"`→5, `"30"`→3, `"10"`→1, else a `(\d+)%`
regex, else the default 3). Afterwards nothing writes it: the Concierge never touches
`MandateStore`, onboarding's routes are session-scoped with no re-run, and the settings screen
sends exactly three keys (`settings_screen.dart:56,59,62`): `risk_score`, `max_drawdown_pct`,
`compliance`. **In practice every user's sector cap is 40%**, because 3 is the default and the
classifier only moves off it on those literal tokens. The mobile l10n note already warns
implementers *"{limit} must come from the response's `max_allowed`, never a hard-coded 0.40 — a
user's mandate `concentration_tolerance` can differ"*: technically true, in practice it rarely
does and never after day one.

**2. Two of the three `risk_components` are dead.** `drawdown_response` and `regret_asymmetry` are
classified by the Concierge, persisted, and echoed back in the mandate readback — and consumed by
**nothing**. Verified: outside the schema and the three constructors that default them
(`concierge_engine`, `brief_engine`, `agent_runner`), there is not one reference in
`backend/app`, and `overlay_generator.py` contains **zero** occurrences of `risk_components`, so
they never reach an agent either. The user answers two risk questions at onboarding that change no
behaviour anywhere. Under the invariant above they must be **wired or deleted** — and putting
sliders on them would ship the DEF129 failure (a control that claims a capability it does not
have) with better UX. **Recommendation: delete both**, or give each a named consumer in this CR.

**3. There are two single-name caps, ~11× apart, and the original scope item 3 does not say which
binds.** The PM clamps to `risk_tier_cap` (max **4.5%** at risk_score 4–5); the floor blocks at
`SINGLE_NAME_ABSOLUTE_CAP_PCT` (**50.0%**). Through the Room path the floor's check can therefore
essentially never fire — 4.5% ≪ 50%. Item 3's *"keep the risk-tier default as the floor"* is
ambiguous between the two. This CR must state plainly which number is the user-facing cap, which
is the backstop, and whether the backstop survives at all. **Under Saiful's rule the answer is
that `SINGLE_NAME_ABSOLUTE_CAP_PCT` becomes user-settable and disclosed like the rest** — it is
the one dial named "absolute", and that name is now the only argument for it, which is not an
argument.

**4. Blocker — the API physically cannot accept a partial risk patch today.**
`MandateStore.patch` (`mandate_store.py:91-113`) is a **shallow merge** with a hand-written special
case for `compliance` alone. `PATCH {"risk_components": {"concentration_tolerance": 4}}` replaces
the entire `RiskComponents` object with a one-key dict; `drawdown_response` and `regret_asymmetry`
are both required (`schemas/mandate.py:57-59`), so the DEF062 re-validation raises → **422**. The
re-validation is correct and must stay; the merge needs the same nested treatment `compliance`
already gets. **This lands before any UI, or the UI ships broken.**

### The combination — how the dials compose

The root design problem is that `concentration_tolerance: int` stores a **proxy** for a limit while
the real number lives in a lookup table the user never sees. That is what makes it un-settable
without inventing a UI for an abstraction.

**Store the limit, not the ordinal.** `concentration_tolerance: int 1–5` → an explicit
`sector_cap_pct`. `_TOLERANCE_TO_CAP` stops being storage semantics and becomes a **preset table**.
Same move for the single-name cap: `DEFAULT_RISK_TIER_CAPS` becomes the preset that `risk_score`
selects, not the enforcement value itself. This collapses "what does tolerance 4 mean" and makes
CR046's shown-equals-enforced invariant trivially true in the UI, because the stored number *is*
the enforced number.

On top of that, three layers:

- **Layer 1 — one Risk Profile dial** (the existing 1–5 slider, relabelled). Moving it writes
  **all** derived limits coherently in one shot: single-name %, sector %, drawdown %. One control,
  coherent by construction, identical UX to today for the user who never opens the next layer.
- **Layer 2 — "Set my own limits"** exposes each cap **in its own units** — single-name cap %,
  sector cap %, max drawdown %, plus every cap this CR adds (max open positions, trades per
  day/week, total open risk, post-loss cooldown). The user enters `35%` because they mean 35%, not
  "tolerance 4". Touching any one detaches the profile dial to **Custom** rather than silently
  fighting it back.
- **Layer 3 — no ceiling, loud disclosure.** *"Set whatever they like"* means the caps reach 100%
  and the cooldown reaches 0. What must not happen is a **silent** 100% (CR040): a value looser
  than the profile's shows its consequence in plain numbers at set-time, and the overlay carries it
  into every agent prompt, so the PM reasons from *"this user has set a 100% single-name cap"*
  rather than being surprised by it. In a simulation-only trainer the blow-up **is** the lesson;
  hiding the dial is not protection, it is opacity — and opacity is the thing CR040 exists to stop.

**Reuse what already exists, do not rebuild it.** `PATCH /v1/mandate/{user_id}` already bumps
`version`, writes a `MANDATE_EDIT` journal entry with a before/after payload, and
`POST /v1/mandate/{user_id}/rollback/{v}` restores any prior version (BL5, AT:R33). Every risk
change is therefore already auditable and revertable — the diff summary at `api/mandate.py:106-113`
just needs extending to name the new fields in plain English, the way it already does for
`max_drawdown_pct` / `risk_score` / `compliance`.

**Define retro-tightening explicitly.** The settings screen already refreshes the sim after a patch
*"so any newly-rejectable holdings show up correctly"*. Tightening a cap below current exposure must
**flag** the affected holdings and let the floor block *new* buys — it must never force-sell or
retroactively invalidate a recorded trade. State this in the build, don't let it be discovered.

### Interaction with CR105

CR105 scope item 2 replaces the bare `50%` literal in `content/agents/portfolio_manager.md` with
wording deferring to the safety-floor block. That is compatible and becomes **more** load-bearing
under this CR: once the cap is per-user, a hardcoded literal in a shared prompt is not merely
drift-prone, it is wrong for every user who changed it. Whichever lands first, the other must not
reintroduce a numeric cap literal into agent copy.

### Amended Scope — added to the six original items

7. **Nested merge for `MandateStore.patch`** so a partial `risk_components` (and any new nested
   risk group) merges instead of replacing. **Prerequisite for items 5 and 8.** Keep the DEF062
   full-schema re-validation.
8. **Store limits, not ordinals** — `concentration_tolerance` → explicit `sector_cap_pct`;
   `_TOLERANCE_TO_CAP` and `DEFAULT_RISK_TIER_CAPS` demoted to preset tables. One migration maps
   existing rows through the current table so no user's enforced cap changes on deploy.
9. **Resolve the two single-name caps** — name which is user-facing and which (if any) is a
   backstop; make `SINGLE_NAME_ABSOLUTE_CAP_PCT` user-settable and disclosed per the rule, or
   delete it and say so.
10. **Wire or delete `drawdown_response` and `regret_asymmetry`.** No slider on an unenforced field.
11. **Overlay disclosure** — every effective cap, in its own units, in the agent overlay
    (`overlay_generator.py` currently exposes none of `risk_components`), so the PM's reasoning and
    the user's screen read the same numbers.
12. **Profile / Custom / no-ceiling UX** — layers 1–3 above, including the CR040 loud disclosure
    when a cap is set looser than its profile value.
13. **Extend the mandate-edit journal diff** to name the new fields in plain English.

## Amended Acceptance — added to the original four

- **The invariant is testable and tested:** one guard enumerates every Mandate field that feeds an
  enforced limit and asserts each is (a) read by a deterministic check, (b) present in the
  overlay, (c) reachable by `PATCH`. A field failing any leg fails the build. This is the guard
  that stops the `concentration_tolerance` situation recurring; the house rule (second occurrence
  ⇒ entry **with** a guard) applies — add it to `failure_patterns.md` naming this check.
- `PATCH {"risk_components": {...one key...}}` returns 200 with the other keys preserved
  (demonstrated **red** against the current shallow merge first).
- Setting a cap to its loosest value (100% / cooldown 0) succeeds, is disclosed at set-time in
  plain numbers, and appears in the agent overlay text — verified by reading an assembled PM prompt.
- Migration proof: for every existing user, the enforced sector cap after migration equals
  `_TOLERANCE_TO_CAP[concentration_tolerance]` before it.
- Tightening a cap below current exposure flags the affected holdings and blocks new buys, and
  force-sells nothing.
- No numeric cap literal survives in any agent copy (shared with CR105 item 2).

---

## Original filing (2026-07-27) — retained

## Why

The CR060 content sweeps found that a slice of the curriculum teaches Mandate constraints the product does
not actually have — the "phantom mandate" class:

- **DEF102** — ~6 lessons teach fields absent from `backend/app/schemas/mandate.py`
  (`cooldown_after_stop_minutes`, `max_open_positions`, `max_trades_per_week`, `max_sector_exposure_pct`,
  `total_open_risk_pct`, `max_single_factor_exposure_pct`).
- **DEF117** — ~26 of 193 daily challenges assume the same caps (21 position-size, 6 sector, 1 concentration,
  1 app-enforced cooldown, 3 max-trades). Whole "spot the violation" challenges hinge on them.

Rather than strip the content down to the product, **build the product up to the content.** These are genuine
risk-management features a training simulator should have; the curriculum was authored to the intended design.

## Scope (build team + audit lane — NOT the education lane)

1. **Schema** — add the fields to `Mandate` (`backend/app/schemas/mandate.py`) with sane bounds/enums, matching
   the existing style (e.g. `max_drawdown_pct` is a `Literal`). Decide each field's type and default.
2. **Enforcement** — deterministic checks in the PM compliance step, as a **hard floor** (the CR038 rule:
   prompt instructions are not controls — make it structural, like the halal floor). A trade breaching a cap is
   blocked with a named reason, same as `is_blocking` in the halal path.
3. **Derived → explicit** — reconcile the currently-DERIVED single-name cap (`risk_tier_cap(risk_score)` in
   `backend/app/trading_math/sizing.py`) with an explicit user-settable concentration cap; keep the risk-tier
   default as the floor.
4. **Overlay** — thread the new caps through `backend/app/agents/overlay_generator.py`.
5. **UI** — surface the caps in the Mandate screen (Settings → Mandate).
6. **Config parity** — anything env-gated forwards in `docker-compose.yml` (CR040 / `test_config_compose_parity`).

## Consequences for content (coordinate)

- **HALT the lesson-strip** of the DEF102 cohort (another lane began stripping 017/047/050/051). Once these
  fields exist, the original lesson content is correct — stripping would now be the regression. Reconcile any
  already-stripped lessons back to the built design.
- Once shipped, DEF102 + the DEF117 phantom-cluster flip from "wrong vs product" to "correct" — re-verify the
  cohort against the built schema and close.
- The `dc_2026_07_22` cooldown challenge specifically claims an *app-enforced* cooldown; lesson 047 teaches a
  *self-imposed* one. The build decides which is true — align both to whatever ships (enforced hard floor vs.
  journal-logged nudge).

## Acceptance

- New Mandate fields exist, validated, defaulted, and config-parity-clean.
- PM compliance blocks a breaching trade deterministically with a named reason; unit-tested.
- Overlay + Mandate UI expose the caps.
- DEF102 + DEF117 phantom cohorts re-verified green against the shipped schema.
