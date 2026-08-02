# CR136 build — M05: Rule engine

> Conforms to CR136 Rev 4 + build/README.md. Where this doc and Rev 4 disagree, Rev 4 wins.

**AUDIT-LANE module** (Rev 4 "Risk class"): submit through `orchestration/audit/`
when built. Depends on M04 (constants module + metric context). Consumed by M06.

## 1. Purpose

Implements Rev 4's "Recommendation rule engine (deterministic — the LLM never
invents advice)": the seven rules R0, R1, R2, R2b, R3, R4, R5 as a pure,
side-effect-free service. Estimated-quantity rules (R1/R2/R2b/R3, plus R4's
convention band) are two-line hysteresis state machines — fire on crossing the
fire line, stay fired until crossing the clear line, initial state cleared (F4).
Accounting rules (R0, R5) mirror their sources exactly, no band. Every value any
template interpolates — including literal threshold mentions like R1's "40" — is
REGISTERED in the rule result's `slots`, which is what closes M06's validator
allow-list category (b) (F15). The engine reads state in, returns state out; it
never touches the DB, the journal, or the LLM.

## 2. Files

**New:**

- `backend/app/services/portfolio_rules.py` — header docstring one-liner:
  `"""CR136 M05 — deterministic Portfolio Health rule engine (R0–R5): hysteresis state machines over the stripped metric context; every interpolated number registered for the M06 validator allow-list. No LLM, no DB."""`
- `backend/tests/unit/test_cr136_rule_engine.py` — header docstring one-liner:
  `"""CR136 M05 — fire/no-fire boundaries at ±ε per Rev 4 acceptance, hysteresis round-trips, R0 agreement with the trade-time mandate gate, slot registration."""`

**Touched:** none. The safety floor, sizing, and sector-allocation modules are
imported, never modified. Constants are added to **M04's constants module**
(this doc pins the NAMES in §3.1; M04's doc pins the module path — build order
is M04 → M05, so the module exists before this one starts. If M04 landed the
constants under a different path, import from there; the names are the contract).

**i18n note:** every template string and the ETF disclosure in §3.4/§3.5 is new
user-visible EN copy — flag `retranslate:[ar,ms]` per the content-change rule.
Copy says AMI by name if it ever names the system; none of these templates do.

## 3. Implementation spec

### 3.1 Constants consumed (by name, from M04's constants module)

Each carries a comment naming its Rev 4 derivation (README convention). Values
are Rev 4 verbatim — do not re-derive:

```python
RULE_R1_FIRE_TOP_RISK_SHARE_PCT = 41.5   # Rev 4 R1: band ±1.5pp = 0.6× measured per-window sd
RULE_R1_CLEAR_TOP_RISK_SHARE_PCT = 38.5
RULE_R1_MIN_RISKY_HOLDINGS = 4           # Rev 4 R1 n-gate: small books have structurally high top shares
RULE_R1_TEXTBOOK_THRESHOLD_PCT = 40      # literal in R1's template — registered in slots (F15)
RULE_R2_FIRE_DR2 = 1.85                  # Rev 4 R2: fire DR² < 1.85
RULE_R2_CLEAR_DR2 = 2.15                 # clear DR² > 2.15; band ±0.15 measured (5.5% flips)
RULE_R2_MIN_HOLDINGS = 8                 # Rev 4 R2 n-gate
RULE_R2B_FIRE_RHO = 0.90                 # Rev 4 R2b; band 0.05 ≈ 3× SE(ρ̂) at ρ=0.9, T=126
RULE_R2B_CLEAR_RHO = 0.85
RULE_R2B_MIN_PAIR_WEIGHT_PCT = 5.0       # each holding of the pair ≥ 5% invested weight
RULE_R3_BETA_BASE = 1.3                  # Rev 4 R3: lines are 1.3 ± 0.6·SE(β̂)
RULE_R3_SE_BAND_MULT = 0.6
RULE_R3_MIN_R2 = 0.2                     # R² co-gate
RULE_R4_FIRE_CASH_PCT = 41.0             # Rev 4 R4: ±1pp convention band around 40
RULE_R4_CLEAR_CASH_PCT = 39.0
ETF_OVERLAP_DISCLOSURE = (               # Rev 4 F21 fixed disclosure — shared with M04's weight tile
    "counts each ETF as one holding; index-fund overlap is not looked through "
    "— your true single-name exposure can be higher."
)
```

R0 has **no constants of its own** — its caps come from the trade gate's own
resolvers at call time (§3.4). No threshold literal may appear in
`portfolio_rules.py` (acceptance §6 greps for this).

### 3.2 Public API

```python
@dataclass(frozen=True)
class HoldingInput:
    ticker: str
    invested_weight_pct: float      # market value / total invested value × 100 (raw sleeve, ALL risky holdings in denominator)
    sector: str                     # GICS sector or "Other" (M04 resolves via the CR026 SectorMap)
    included: bool                  # True = in the EWMA Σ; False = dropped
    drop_reason: str | None = None  # "short_history" | "data_quality" when included=False
    risk_share_pct: float | None = None  # invested-basis risk share (sums to 100 over included); None when not included or block insufficient


def evaluate_rules(
    *,
    mandate: Mandate,                    # app.schemas Mandate — the user's live mandate
    holdings: list[HoldingInput],        # ALL risky holdings (included + dropped); cash is NOT a row
    dr2: float | None,                   # DR² block value; None when insufficient
    beta: float | None,                  # β̂ from the joint EWMA Σ; None when insufficient
    se_beta: float | None,               # WLS SE(β̂) (T_eff); None when insufficient
    r2: float | None,                    # weighted ρ²; None when insufficient
    beta_window_days: int | None,        # window_days of the beta block (R3's {window} slot)
    cash_pct_total: float,               # cash as % of TOTAL portfolio value (accounting, always available)
    pairwise_rho: list[tuple[str, str, float]] | None,  # (a, b, ρ) upper triangle over INCLUDED holdings, from the SAME joint EWMA matrix; None when Σ insufficient
    contains_etfs: bool,
    rule_states: dict[str, str] | None = None,  # prior states from the newest prior Finding payload; None/missing keys = "cleared" (first run)
) -> tuple[list[dict], dict[str, str]]:
```

Returns `(results, updated_rule_states)`.

- `results`: exactly **7 dicts, in order `R0, R1, R2, R2b, R3, R4, R5`**, each
  the README contract-3 shape: `{"rule_id": str, "fired": bool, "state":
  "fired"|"cleared", "slots": {...}, "based_on": [metric ids]}`. `fired` ≡
  `state == "fired"` after this evaluation — a rule in the fired state renders
  its template in every Finding until it clears (that is the point of
  hysteresis: no flap in/out between reports).
- `updated_rule_states`: `{"R0","R1","R2","R2b","R3","R4","R5"} →
  "fired"|"cleared"` — ALL seven keys, always. M06 persists this dict verbatim
  in the Finding payload (`rule_states`) and reads it back from the newest prior
  Finding for the same `portfolio_id` (the same read the idempotency check does
  — M06's job, not this module's).

The function is pure: no I/O, no clock, no randomness. `mandate` is the only
non-primitive input; it is read via the trade gate's resolvers only.

### 3.3 Hysteresis core

```python
def _step(state: str, value: float, fire_line: float, clear_line: float, *, low_is_bad: bool = False) -> str
```

High-is-bad (R1, R2b, R3, R4): from `cleared`, → `fired` when `value >=
fire_line`; from `fired`, → `cleared` when `value < clear_line`; otherwise state
unchanged. Low-is-bad (R2): from `cleared`, → `fired` when `value < fire_line`;
from `fired`, → `cleared` when `value > clear_line`; otherwise unchanged.
(Boundary semantics are exactly these operators — Rev 4 writes R1 fire "≥
41.5%", clear "< 38.5%"; R2 fire "< 1.85", clear "> 2.15"; R2b fire "ρ ≥ 0.90",
clear "ρ < 0.85"; R3 fire "β̂ ≥ …", clear "β̂ < …"; R4 fire "≥ 41%", clear "< 39%".)

**Gate-unmet ⇒ forced `cleared`.** When a rule's n-gate/co-gate fails or a
required input is `None` (insufficient block — M06 hands the engine the same
stripped truth the LLM sees), the rule cannot cite a current number, so it
cannot stay fired: state := `cleared`, `fired = False`, slots empty. This is the
pinned reading of Rev 4's "the rule stays silent" for gated books — no alarm
without a measurement (CR040), and a fired rule with stripped inputs would have
nothing registered to render. R0/R5 skip `_step` entirely: their state mirrors
the current condition every run (Rev 4: "Accounting rules (R0, R5) mirror their
source exactly and carry no band").

### 3.4 R0 — mandate check (mirror the trade gate; never re-derive)

Rev 4 verbatim — fire: "any holding's invested weight > its resolved mandate
cap, or a sector > the resolved sector cap — computed by the same resolvers the
trade gate uses"; clear: "mirror of fire"; template:

> "Your mandate caps a single {scope} at {cap}%. {name} is at {weight}% of
> invested value today." + ETF disclosure when `contains_etfs`

**Verified trade-gate semantics (read before coding; mirror these exactly):**

- **Single-name cap:** import `single_name_cap_pct` from
  `app.agents.safety_floor` (defined `safety_floor.py:50-75`). Post-CR129 it
  resolves `mandate.single_name_cap_pct` override → else the **risk-tier preset**
  `DEFAULT_RISK_TIER_CAPS = {1: 1.5, 2: 1.5, 3: 3.0, 4: 4.5, 5: 4.5}`
  (`trading_math/sizing.py:22`, via `resolved_single_name_cap_pct`,
  `sizing.py:73`). The flat `SINGLE_NAME_ABSOLUTE_CAP_PCT = 50.0`
  (`sizing.py:35`) is **no longer the floor's fallback** — it survives only as
  the debate-spread ceiling. Do NOT hard-code 50 anywhere in R0.
  Comparison is **strict `>`**, mirroring `safety_floor.py:369`
  (`position_pct > cap_single_name`) and `:631` (held-position audit).
- **Sector cap:** import `sector_concentration_cap` from
  `app.services.sector_allocation` (defined `sector_allocation.py:145-159`) —
  returns a **fraction 0–1**: `mandate.sector_cap_pct` (percentage points,
  nullable — `schemas/mandate.py:162`) when set, else the
  `concentration_tolerance`-keyed preset
  `DEFAULT_CONCENTRATION_TOLERANCE_CAPS = {1: 25.0, 2: 30.0, 3: 40.0, 4: 50.0,
  5: 60.0}` (`sizing.py:43-45`, via `resolved_sector_cap_pct`, `sizing.py:87`),
  else 0.40. Comparison mirrors `sector_allocation.py:238`:
  `weight_frac > cap_frac + 1e-9`. The `"Other"` bucket **never breaches**
  (DEF059 guard, `sector_allocation.py:43/:52`); cash is not a sector row here
  by construction (invested sleeve).
- The trade-time enforcement path is `check_mandate_compliance`
  (`app/agents/safety_floor.py:173`, called from `sim_engine.py:607-628`) and
  its held-position sibling `check_holdings_against_mandate`
  (`safety_floor.py:563`). Importing the two resolvers above — not copying
  their values — is what guarantees the cap NUMBER shown by R0 can never differ
  from the number the gate enforces (the CR046 shown == enforced invariant).

**Evaluation:** per-holding, `invested_weight_pct > single_name_cap` (strict);
per-sector, sector invested weight (sum of member holdings'
`invested_weight_pct`, dropped holdings included — a dropped-for-data holding
still counts toward its cap) vs `sector_concentration_cap(mandate) × 100` with
the `1e-9` fraction-epsilon mirrored. **Basis is TOTAL-VALUE weight.**

> **AMENDED 2026-08-02 (AT:R66), after the M05 audit.** This section originally
> said invested-sleeve, and the shipped code followed it. That is wrong: Rev 4's
> R0 row and build/README.md's seam register ("R0 is total-value basis", already
> folded in as an amendment to Rev 4 itself) both pin TOTAL-VALUE, and the
> README overrides the module doc. Measured on a $10,000 book with 50% cash and
> a 35% single-name cap: the trade gate reported ZERO violations while an
> invested-sleeve R0 reported three — the shown-vs-enforced split CR046 closed,
> inverted, with the report accusing the user of a breach their own trade ticket
> denies. The agreement test could not catch it because it ran only at cash = 0,
> the single point where the two bases coincide; a cash > 0 case now exists.
>
> The sentence that stood here — "invested weight ≥ total-value weight whenever
> cash ≥ 0, so R0 is a conservative superset of the gate's check" — was the
> pre-fix reasoning and is now deleted. It was true arithmetic used to excuse
> the wrong basis: a *superset* of the gate is exactly the defect, because the
> extra members are books the gate calls compliant and R0 called breaches.

**Slots:**

```python
{"breaches": [{"scope": "name"|"sector", "cap_pct": <resolved cap, exact float>,
               "name": <ticker or sector>, "weight_pct": <round(w, 1)>}],
 "etf_disclosure": <bool>}   # True iff fired and contains_etfs; M06 appends ETF_OVERLAP_DISCLOSURE
```

M06 renders the template once per breach entry. Fired iff `breaches` non-empty.
`based_on: ["total_value_weights", "sector_weights"]` — the basis the shipped
rule actually uses, and the one the result's `basis: "total_value"` field
declares.

### 3.5 R1–R5 — conditions, templates (Rev 4 verbatim), slots

| Rule | Fire | Clear | Gate(s) |
|---|---|---|---|
| **R1** | top risk share ≥ **41.5%** AND risky holdings ≥ **4** | < **38.5%** | included-holdings count ≥ `RULE_R1_MIN_RISKY_HOLDINGS`; risk shares present |
| **R2** | DR² < **1.85** AND holdings ≥ 8 | > **2.15** | included-holdings count ≥ `RULE_R2_MIN_HOLDINGS`; `dr2` not None |
| **R2b** | any pair of holdings each ≥ 5% invested weight with ρ ≥ **0.90** | ρ < **0.85** | `pairwise_rho` not None; pair qualifies iff BOTH tickers' `invested_weight_pct` ≥ 5.0 |
| **R3** | β̂ ≥ 1.3 + **0.6·SE(β̂)** AND R² ≥ 0.2 | β̂ < 1.3 − **0.6·SE(β̂)** | `beta`/`se_beta`/`r2` not None; `r2 >= RULE_R3_MIN_R2` |
| **R4** | cash ≥ 41% of total value | < 39% | none (accounting; always evaluable) |
| **R5** | any `partial: true` (i.e. any holding with `included=False`) | mirror | none |

Templates — **fixed strings, Rev 4 verbatim**, module-level
`RULE_TEMPLATES: dict[str, str]` in `portfolio_rules.py` (M06 imports them; the
deterministic fallback ships these same strings):

- **R1:** "When a single position accounts for more than 40% of a portfolio's
  risk, the textbook response is to consider whether the concentration is
  intentional. Here, {ticker} accounts for {risk_share}% of risk while holding
  {weight}% of invested value." *(The old per-dollar phrasing is FALSE — F3;
  MCR owns per-dollar statements, M04. Never reintroduce it.)*
- **R2:** "You hold {n} positions but about {dr2} effective independent bets —
  they have tended to move together. Textbook practice adds exposures that
  behave differently, not more of the same."
- **R2b:** "{a} and {b} moved almost identically over the window (correlation
  {rho}). Two holdings that move together provide less diversification than
  two that don't."
- **R3:** "β = {beta} (market explains {r2_pct}% of daily moves; {window}-day
  window) — this book has moved about {beta}× the S&P 500 over the measured
  window." *(NO projection clause — F5 deleted it. Nothing about what the book
  "would" do in a 10% move.)*
- **R4:** "{cash}% of your book is cash. Cash scales the whole-book volatility
  and beta down in proportion — it does not change how concentrated the
  invested sleeve is: risk shares and effective bets are unchanged by it."
  *(Rewritten in Rev 4 — F9: cash scales σₚ and β exactly ×(1−c), leaves risk
  shares/DR²/R² exactly invariant. Never "dilutes every risk number".)*
- **R5:** "Metrics exclude {dropped} ({reasons}). Treat the numbers as
  describing {covered}% of your invested value."

**Per-rule slot dicts** (keys = template placeholders + registered literals;
every numeric leaf is a validator category-(b) member):

- R1: `{"ticker": str, "risk_share": round(top_share, 1), "weight":
  round(top_holding.invested_weight_pct, 1), "threshold_mention":
  RULE_R1_TEXTBOOK_THRESHOLD_PCT}` — the template's literal "40" is registered
  via `threshold_mention` even though it is not a format slot (F15 corollary;
  the brief's explicit pin).
- R2: `{"n": <included count, int>, "dr2": round(dr2, 1)}`.
- R2b: `{"a": str, "b": str, "rho": round(rho, 2)}` — the **highest-ρ
  qualifying pair**. Fire when ANY qualifying pair ρ ≥ 0.90; while fired, stays
  fired while any qualifying pair ρ ≥ 0.85; clears when no qualifying pair
  remains ≥ 0.85 (a pair whose weight drops below the floor stops qualifying).
- R3: `{"beta": round(beta, 2), "r2_pct": round(r2 * 100), "window":
  beta_window_days}`. The template's "500" (S&P 500) is on M06's fixed
  constants list (validator category c) — the engine does not register it.
  Note the template's plain-language R² form ("market explains X% of daily
  moves") is deliberate: the literal "R²" would trip M06's register check.
- R4: `{"cash": round(cash_pct_total, 1)}`.
- R5: `{"dropped": [tickers with included=False], "reasons": [their
  drop_reasons, deduplicated, e.g. "short history", "data quality"],
  "covered": round(sum of included holdings' invested_weight_pct, 1)}` —
  `{covered}` pinned to invested-value basis (1 − dropped/invested), matching
  the template's own words and the 20% sufficiency rule.

**Slot values are the trigger values**: rounded renderings of the exact numbers
the fire/clear decision used in THIS evaluation — never recomputed, never a
different observation. Decisions use unrounded inputs; slots carry the rounded
form M06 renders verbatim.

`based_on` (informational, nothing branches on it): R1
`["risk_contribution"]`, R2 `["dr_squared"]`, R2b `["correlation_matrix"]`, R3
`["beta_r2"]`, R4 `["cash_allocation"]`, R5 `["dropped_holdings"]` — align the
strings to M04's frozen metric ids at build time if they differ.

## 4. Out of scope for this module

- **Template rendering, interpolation, §F5 assembly** — M06. M05 only exports
  `RULE_TEMPLATES` + registered slots.
- **The validator** (allow-list, register lexicon, rejection path) — M06. M05's
  contribution is complete slot registration.
- **Reading/persisting `rule_states`** (journal read of the newest prior
  Finding, payload write) — M06/M08. M05 is pure: dict in, dict out.
- **Metric computation** (Σ, DR², β, SE, risk shares, ρ, weights, sufficiency)
  — M02/M04. M05 trusts its inputs and never recomputes.
- **Trade-time enforcement** — untouched. `safety_floor.py`, `sizing.py`,
  `sector_allocation.py` are imported read-only; no behaviour change there.
- **API, gating, mobile** — M07/M09.
- ETF constituent look-through — follow-up CR; R0 ships the disclosure only.

## 5. Tests

`backend/tests/unit/test_cr136_rule_engine.py`, sqlite-free (pure function —
no fixtures beyond constructed inputs). Boundary cases per Rev 4 acceptance:

**R0 (cap ±0.1pp + gate agreement):**
1. Explicit `single_name_cap_pct=35.0`: holding at 35.1 fires; 34.9 not;
   **35.0 exactly does NOT fire** (strict `>`, mirroring `safety_floor.py:369`).
2. CR129 default semantics: `single_name_cap_pct=None`, `risk_score=3` → cap
   resolves to **3.0** (risk-tier preset), NOT 50.0; holding at 3.1 fires.
3. Sector: `sector_cap_pct=None`, `concentration_tolerance=3` → 40%; a sector
   at 40.1 fires, 39.9 not; `"Other"` at 60% never fires.
4. **Agreement with `check_mandate_compliance` on identical inputs** at cash=0
   (bases coincide): (a) the holdings R0 flags for single-name are exactly the
   holdings `check_holdings_against_mandate` reports with the cap issue; (b)
   with Tech at 40.1%/cap 40%, a marginal Tech BUY through
   `check_mandate_compliance` (holdings+quotes+sector_map supplied) is blocked
   AND R0 fires on the same book; both flip together at cap ±0.1pp.
5. `contains_etfs=True` + fired ⇒ `slots["etf_disclosure"] is True`; not fired
   ⇒ no disclosure flag.

**R1:** fire at 41.6, not 41.4, fire at exactly 41.5 (n=4 throughout); n-gate:
top share 45.0 with 3 included holdings silent, 4 fires; from `fired`: 38.6
stays fired, 38.4 clears; from `fired`, n drops to 3 ⇒ forced cleared; slots
carry `threshold_mention == 40` and `risk_share` == round(trigger, 1).

**R2:** fire at 1.84, not 1.86 (n=8); n-gate 7/8; from `fired`: 2.14 stays,
2.16 clears; `dr2=None` ⇒ cleared.

**R2b:** pair weights 6/6: ρ 0.901 fires, 0.899 not, 0.90 exactly fires (≥);
weight floor at ρ=0.95: weights 4.9/4.9 silent, 5.1/5.1 fires; from `fired`:
ρ 0.86 stays fired, 0.84 clears; three-pair book: slots carry the highest-ρ
qualifying pair; fired pair's weight drops below 5% and no other qualifying
pair ≥ 0.85 ⇒ clears.

**R3:** with `se_beta=0.05` (lines 1.33/1.27): β̂ 1.3301 fires, 1.3299 not;
co-gate at β̂ 1.35: r2 0.19 silent, 0.21 fires; from `fired`: β̂ 1.271 stays,
1.269 clears; `r2` drops below 0.2 while fired ⇒ forced cleared; `beta=None` ⇒
cleared. (±ε around 0.6·SE per the brief: ε = 1e-4 on β̂ is fine.)

**R4:** 41.1 fires, 40.9 not; from `fired`: 39.1 stays, 38.9 clears.

**R5:** weights 40/30/30, one 30 dropped (`short_history`) ⇒ fires,
`covered == 70.0`, reasons rendered; no drops ⇒ cleared (partial toggle).

**Hysteresis round-trip:** evaluate → feed `updated_rule_states` back with
between-the-lines values (R1 at 40.0, R2 at 2.00, R2b at 0.87, R3 mid-band, R4
at 40.0) → every fired state stays fired AND every cleared state stays cleared
(run both starting states); `rule_states=None` (first run) ⇒ all seven cleared;
unknown/missing key defaults cleared.

**Shape + registration:** always exactly 7 results in order
`[R0,R1,R2,R2b,R3,R4,R5]`; all seven keys in `updated_rule_states` with values
in `{"fired","cleared"}`; `fired == (state == "fired")` for every rule.
**Template literal audit:** regex every digit-run in `RULE_TEMPLATES`; assert
the set is exactly `{"40"}` (R1, registered) ∪ `{"500"}` (R3, M06 fixed
constant) — any new literal fails the build (F15 closure).
**Rendered slots match trigger values exactly:** for each fired rule, the slot
number equals `round()` of the same input that crossed the line.

## 6. Acceptance

Checklist a reviewer runs on the Mac (pure-editor rules):

- [ ] `pytest backend/tests/unit/test_cr136_rule_engine.py -q` green; full
      `pytest backend/tests/unit/ -q` green.
- [ ] `grep -n "from app.agents.safety_floor import" backend/app/services/portfolio_rules.py`
      shows `single_name_cap_pct` imported (not re-derived);
      `grep -n "from app.services.sector_allocation import"` shows
      `sector_concentration_cap` imported.
- [ ] `grep -En "41\.5|38\.5|1\.85|2\.15|0\.90|0\.85|5\.0|1\.3|0\.6|0\.2|41\.0|39\.0" backend/app/services/portfolio_rules.py`
      matches nothing outside comments — all thresholds arrive by name from
      M04's constants module (README "never scattered literals").
- [ ] `grep -c "50" backend/app/services/portfolio_rules.py` shows no
      hard-coded 50% single-name fallback (CR129 semantics respected).
- [ ] `RULE_TEMPLATES` strings match Rev 4's table verbatim (diff against the
      Rev 4 rule table); R3 contains no projection clause; R1 contains no
      per-dollar claim.
- [ ] Every numeric leaf of every fired rule's `slots` is a value the engine
      itself computed or a registered literal — reviewer spot-checks R1's
      `threshold_mention`.
- [ ] New EN template strings flagged `retranslate:[ar,ms]` in the commit/CR
      notes.
- [ ] Commit tagged `(AT:R<N> CR136)`, pathspec-commit only; module submitted
      to the audit lane (`orchestration/audit/`) per Rev 4's risk class.

## 7. Hand-off

After M05 lands, M06 may assume:

- `from app.services.portfolio_rules import evaluate_rules, RULE_TEMPLATES,
  HoldingInput` with the exact §3.2 signature; pure and deterministic.
- `results` is always 7 entries in fixed order with the README contract-3
  shape; `fired == (state == "fired")`; a fired rule's `slots` contains every
  number its template needs, at render precision — interpolate and register,
  never compute. Validator category (b) = the numeric leaves of `slots` across
  all results (walk nested lists/dicts — R0's `breaches` is nested).
- `updated_rule_states` is complete (all 7 keys) and safe to persist verbatim;
  passing it back unchanged with unchanged inputs is idempotent.
- R0's `slots["etf_disclosure"]` flags when to append `ETF_OVERLAP_DISCLOSURE`
  (constant lives in M04's constants module, shared with the weight tile).
- Gate-unmet/insufficient inputs have already been resolved to `cleared` —
  M06 never needs to second-guess a rule against sufficiency flags; it only
  strips insufficient metric blocks from the LLM context (its own job) and
  maps M04's context onto `evaluate_rules` arguments (`HoldingInput` rows:
  raw invested-sleeve weights including dropped holdings; `pairwise_rho` from
  the joint EWMA matrix; `beta_window_days` from the beta block).
- The trade gate (`safety_floor.py`, `sizing.py`, `sector_allocation.py`) is
  behaviourally untouched — M05 added no code path to it.
