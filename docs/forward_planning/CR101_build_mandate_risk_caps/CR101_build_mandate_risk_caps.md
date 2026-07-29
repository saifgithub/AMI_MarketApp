# CR101 — Build the Mandate risk caps the curriculum already teaches

**Filed:** 2026-07-27 · **Status:** proposed · **Decision:** Saiful, 2026-07-27 — *"create a CR for the caps. It will be build."*
**Amended:** 2026-07-29 (AT:R59, room-quality) — Saiful, verbatim: **"All risk parameters must be disclosed and user-settable."** Read Amendment 1 first; it adds a governing principle, an audit of what exists today, one blocker that must land first, and a schema decision the original scope left open.

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
