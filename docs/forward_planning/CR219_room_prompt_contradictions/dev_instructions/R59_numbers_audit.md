# R59 — the numbers audit, phase 1 inventory

**Status: READ-ONLY inventory. Nothing here is built.** Phase 2 (fixes + the
guard) is dispatched separately after the dispatcher reviews these findings.

Scope per [`WP12_R59_numbers_audit.md`](WP12_R59_numbers_audit.md): every number
the user reads from **the verdict card**, **the Room transcript**, and **the
1-on-1 surface**. Journal/lessons are out of scope (different pipelines) — but
note the Journal replays the *same* persisted verdict JSONB through
`room_board_mappers.dart`, so every verdict-card finding below is inherited by
the Journal board verbatim.

**Line numbers are against committed `HEAD` (`6394a3dc`), not the working
tree.** *(Dispatcher correction 2026-09-03: the original header said `f5aa5f3a`,
but that commit's `room_runner.py` is 5,730 lines — the 6,082-line file every
citation was verified against IS `6394a3dc`; spot-checks confirm the line
numbers are right and only this label was wrong.)* `room_runner.py` and `room_prompts.py` were dirty from another lane
during this audit and shifted twice mid-pass, so citing the working tree would
have produced references that rot within the hour. Spot-check with
`git show HEAD:<path>`; at HEAD `room_runner.py` is 6,082 lines. Every
`file:line` below was read, not grepped and assumed.

---

## 1. Summary

| Class | Count |
|---|---|
| computed-in-code | 14 |
| code-checked / rewritten | 6 |
| **LLM-unverified** | **7** |
| **Total numerics inventoried** | **27** |

The headline: **the verdict card's structured fields are in good shape.** Every
numeric the card renders as a *field* is either computed in code, clamped in
code, or provenance-tagged. The exposure is almost entirely in **free prose** —
`verdict.reason`, the transcript's analyst turns, and the 1-on-1 surface — where
a number can be stated without ever passing a parser, because nothing in those
paths parses arbitrary prose numerals at all.

The single most important structural fact for phase 2: the existing checks
(`_verify_and_annotate_geometry`, `_annotate_rr_against_levels`,
`_annotate_direction_against_price`) are all **trigger-gated on a recognised
shape**. They fire when the text states a full entry/stop/target triple, or a
keyword-anchored R:R, or a directional instruction near a structured level. A
number stated in any *other* shape — a percentage, a multiple, a dollar figure, a
share count, a growth rate — is not merely unchecked; it is **outside the reach
of every check that exists**. That is the finding class, not any individual
number.

---

## 2. Inventory

### 2.1 The verdict card — structured API fields

Schema: `backend/app/schemas/room.py:34-153`. Client read sites:
`mobile/lib/models/room_board_mappers.dart:131-153`.

| Field | Provenance | Class | Evidence |
|---|---|---|---|
| `action` | LLM-stated, grammar-pinned to `["APPROVE","PASS"]`, then normalised, then floor-vetoed | code-checked | `room_prompts.py:612`; `room_runner.py:1469` (`_normalize_pm_action`); floor at `room_runner.py:4912` |
| `size_pct` | LLM-stated, **clamped** to the mandate risk-tier ceiling in code; an APPROVE with no usable size fails safe to no-verdict | code-checked | parse `room_runner.py:1978-1981`; ceiling `room_runner.py:1078` (`_risk_tier_size_ceiling`); clamp `room_runner.py:2023-2025` |
| `entry` | LLM-stated, else the Trader's number; provenance recorded | code-checked | `room_runner.py:1988-1990`; provenance `room_runner.py:2056-2058` |
| `stop` | LLM-stated, else **minted in code** at `entry * 0.94` and disclosed | computed-in-code (on the default path) | `room_runner.py:2004`; disclosure `room_runner.py:2026-2031`; provenance `room_runner.py:2059-2060` |
| `target` | LLM-stated, else **minted in code** at `entry * 1.13` and disclosed | computed-in-code (on the default path) | `room_runner.py:2005`; same disclosure/provenance sites |
| `time_horizon_days` | LLM-stated; falls back to `ctx.trader_horizon_weeks * 7`. **Bounded by nothing.** | LLM-unverified → **F4** | `room_runner.py:2010-2012`; grammar is a bare nullable integer, `room_prompts.py:617` |
| `level_provenance` | built in code from which source supplied each price | computed-in-code | `room_runner.py:2056-2062` |
| `violations` | emitted by `enforce_safety_floor`, never LLM | computed-in-code | `room_runner.py:4912` (call site) |
| `opinions_not_included` | filled deterministically from `ctx.withheld` | computed-in-code | `room_runner.py:3345-3355` (`_assemble_no_verdict`); schema note `schemas/room.py:48-52` |
| `approve_votes` / `samples` | counted in code over the self-consistency samples | computed-in-code | `room_runner.py:5662` (`_vote_pm_samples`); schema `schemas/room.py:71-72` |
| `scripted_turns` / `scripted_agents` | counted in code from the fallback path | computed-in-code | fallback `room_runner.py:5215` (`_fall_back_to_script`); schema `schemas/room.py:106-111` |
| `structure.*` (every numeric: `contracts`, `days_to_expiry`, legs, `metrics`, greeks, `payoff_curve`, `spot`) | **entirely computed by `option_strategist` off a chain the server read**; the PM only picks an index | computed-in-code | `schemas/options.py:88-95` (explicit: "None of it is ever model-stated"); construction `room_runner.py:2075-2077`; index resolution `room_runner.py:1801` (`_resolve_pm_structure`); index bounded by the grammar, `room_prompts.py:603-609` |
| `kill_criterion` | LLM free text, length-bounded only. May quote a number. | LLM-unverified → **F6** | `room_runner.py:1703` (`_pm_kill_criterion`); schema note is explicit that the sheet-quantity property is "asked for in the prompt and measured by a scorer, not enforced here" — `schemas/room.py:99-104`; grammar rationale `room_prompts.py:625-634` |
| `reason` | LLM narration + **code-appended** annotations. The narration half is unbounded prose. | mixed — see **F1** | narration `room_runner.py:1738` (`_pm_narration`); appended clauses `room_runner.py:2023-2046` |

**The card's own fields are the strong half of this audit.** Only
`time_horizon_days`, `kill_criterion`, and the narration half of `reason` are
unverified, and of those only `reason` is high-harm.

### 2.2 The verdict card — code-appended clauses inside `reason`

These are worth listing separately because they are the *counter-example*: the
house pattern working. Each is a number the user reads on the card that no model
ever touched.

| Clause | Class | Evidence |
|---|---|---|
| "sized down to X% — mandate risk-tier ceiling" | computed-in-code | `room_runner.py:2025` |
| "defaulted to a ~6%/13%-from-entry protective level" | computed-in-code | `room_runner.py:2028-2031` |
| Concentration note ("this is X% of the portfolio in one name") | computed-in-code | `room_runner.py:1037` (`_concentration_note`), emitted `room_runner.py:2041` |
| Horizon-coherence note (stop distance % vs horizon) | computed-in-code | `room_runner.py:1605-1651` (`_horizon_coherence_note`), emitted `room_runner.py:2046` |
| Option-structure clause ("N contracts, expiry …") | computed-in-code | `room_runner.py:2078-2084` |
| Direction-vs-price correction (close, level, gap %) | code-checked | `room_runner.py:2967` (`_annotate_direction_against_price`), applied `room_runner.py:5037-5049` |

### 2.3 The Room transcript — numeric classes in turn prose

| Class | Provenance | Class | Evidence |
|---|---|---|---|
| **RO ladder figures** — every rung's `size_pct`, `contribution_pts`, `headroom_after_pts`, `share_of_cap_pct`, `reward_risk` | **computed by `build_option_ladder`; the model may only quote them.** Renderers iterate the *ladder's* rows, never the payload, so an invented size has no rung and is dropped | computed-in-code | ladder `trading_math/option_ladder.py:63-119`; math `trading_math/risk.py:26-38` (`drawdown_contribution`); render `risk_officer.py:318-328` (`_rung_head`), `risk_officer.py:340-450` (`render_officer_turns`); the guarantee is stated at `risk_officer.py:348-352` and enforced at `risk_officer.py:380-381` (loop over `rows`) |
| RO `recommended` size | LLM-stated but **only renders when it matches a real rung** | code-checked | `risk_officer.py:370-377`, rendered `risk_officer.py:421-424` |
| RO `confidence` | LLM-stated, enum-validated against `_CONFIDENCE_VALUES` | code-checked | `risk_officer.py:367-369`; grammar `risk_officer.py:198` |
| RO `key_number` / `decisive_number` | **LLM free text, explicitly a "quotation from the fact sheet" — asked for, never verified.** Bounded to 60 chars and rendered verbatim | LLM-unverified → **F2** | instruction `risk_officer.py:79-80`; bound `risk_officer.py:113`; rendered `risk_officer.py:411-413` and `risk_officer.py:425-427`; promoted to the comb headline at `risk_officer.py:416-418, 440` |
| **Trader block** Entry/Stop/Size/Target/R:R | LLM-stated in a **grammar-pinned block** (money regex, size regex, `R:R \d{1,2}\.\d{1,2}:1`), then the triple is **recomputed and the narrated R:R rewritten in place** | code-checked | grammar `room_prompts.py:853-866`; verification `room_runner.py:3269-3327` (`_verify_and_annotate_geometry`), applied to **every agent** at `room_runner.py:5358-5362`; rewrite `room_runner.py:2323-2427` |
| Stance-envelope `SIZE:` | LLM-stated, bounded `0 < x <= 100`, **measurement channel only — not rendered** | code-checked | `room_runner.py:3218-3220`; the "measurement channel, not a rendered one" note is at `room_runner.py:3213-3215` |
| Stance-envelope `HEADLINE:` | LLM free text, **nulled (never truncated) when over-length**. May contain a number | LLM-unverified → **F3** | `room_runner.py:3203-3206`; the null-don't-cut rule and its reasoning are stated there |
| Analyst-cited sheet figures (P/E, ATR, 52-wk range, earnings date, margins, debt) in prose | **The sheet itself is code-built and correct; the analyst's *restatement* of it in prose is unchecked.** No parser reads analyst prose numerals | LLM-unverified → **F1** | sheet build `room_runner.py:619` (`_profile_for_ticker`), ATR at `room_runner.py:798`, forward-P/E clause `room_runner.py:536`; **no verification site exists** — the only prose check, `_verify_and_annotate_geometry`, returns untouched unless a full entry+stop+target triple is present (`room_runner.py:3304-3305`) |
| Derived arithmetic in analyst prose (growth rates, multiples, "X% off the high", implied upside) | **Nothing computes or checks these.** Same gate as above | LLM-unverified → **F1** | `room_runner.py:3304-3305` is the gate that lets all of it through |
| Truncation mark | computed-in-code, keyed on `finish_reason`, never inferred from text shape | computed-in-code | `room_runner.py:3247-3266` (`_mark_if_truncated`) |
| Cap-in-shares clause (dollars + share count in the prompt) | computed-in-code; renders nothing when an input is missing | computed-in-code | `room_prompts.py:2002-2034` (`_cap_in_shares_clause`); `trading_math/portfolio.py:42-51` (`shares_for_size`) |

### 2.4 The 1-on-1 surface

| Class | Provenance | Class | Evidence |
|---|---|---|---|
| Every number in an agent's 1-on-1 reply | **LLM free prose. No verification of any kind.** | LLM-unverified → **F5** | `backend/app/api/one_on_one.py` is 241 lines and contains **no** call to `_verify_and_annotate_geometry`, `_annotate_rr_against_levels`, `_annotate_direction_against_price`, `risk_reward`, `drawdown_contribution`, or any `trading_math` import — verified by grep over the whole file; the only `room_runner` mention is a comment about refund ordering at `one_on_one.py:200` |

This is the widest single gap in the audit: the same twelve agents, the same
fact sheet, the same user, and **none** of the Room's five verification sites.

---

## 3. LLM-unverified findings, ranked by user harm

### F1 — Analyst prose numerals are wholly unverified (highest harm)

**What.** Any number an analyst states in prose that is not part of a full
entry/stop/target triple passes through untouched. This includes restated sheet
figures (a P/E, a margin, a debt load), derived arithmetic (growth rates,
implied upside, "X% off the 52-week high"), and dollar figures.

**Where it lands.** The streamed transcript the user watches, the persisted
transcript, the Journal replay — *and* every downstream agent's prompt, because
the transcript is what the Room reasons from (`room_runner.py:5397-5408`).

**Why nothing catches it.** `_verify_and_annotate_geometry` returns the text
unchanged unless all three of entry/stop/target parse
(`room_runner.py:3304-3305`). That is by design — it is a *geometry* check — but
it means the Room has no numeric check of any other kind on prose.

**Worst plausible error.** An analyst misstates a sheet figure it was handed
correctly (the exact shape of the §13 probe: the live model got the conclusion
right and mislabelled the figure in the parenthetical). The user reads a wrong
P/E or a wrong debt load under an agent's name, **and** the four downstream
phases reason from it, so a single misquote propagates into the RO's
`key_number`, the CIO's narration, and the verdict `reason`. The codebase already
has a four-instance record of exactly this class in the *arithmetic* half —
DEF066 → DEF235 → DEF241 → CR166 Tier D, recited at
`trading_math/option_ladder.py:16-22`.

**Fix class.** *Check-and-rewrite*, narrowly: the sheet is code-built, so the
set of figures an analyst is *entitled* to quote is known. A checker that
extracts labelled numerals from prose and compares them against the sheet's own
values — annotating a mismatch in the established `[AMI …]` voice rather than
vetoing — reuses the whole existing annotation machinery. Do **not** attempt to
verify derived arithmetic in the same pass; that is a separate, harder problem
and belongs in the *strip*/precompute lane.

### F2 — RO `key_number` / `decisive_number` are unverified quotations

**What.** The Risk Officer is instructed to quote a figure from the evidence and
"do not compute anything new" (`risk_officer.py:79-80`). Nothing enforces that
the string is a quotation, that the figure appears in the sheet, or that it is
arithmetically anything at all. It is a 60-char free string
(`risk_officer.py:113`).

**Where it lands.** Rendered verbatim as "Key figure:" on each of the three risk
voices (`risk_officer.py:411-413`) and as "decided by …" on the balanced call
(`risk_officer.py:425-427`). Worse, it is **promoted into the comb headline**
(`risk_officer.py:416-418, 440`) — the single most-read string on the risk hexes.

**Why this is sharper than it looks.** CR197's entire premise is that the model
never emits a computed number (`risk_officer.py:26-30`). That is true of the
*sizes* and the *drawdown figures* — structurally, and impressively so. But
`key_number` is a hole in exactly that claim: it is the one field where a number
the model authored reaches the screen unmediated, on the surface built to
guarantee it cannot.

**Worst plausible error.** The officer "quotes" a drawdown or cap figure it
actually recomputed and got wrong, and it renders in the headline slot beside
the genuinely-computed rung figures — where its provenance is visually
indistinguishable from them. That is DEF066's error re-entering through the one
door CR197 left open.

**Fix class.** *Check-and-rewrite*. The sheet and the ladder are both in hand at
render time; a `key_number` whose numerals do not appear in either is either
struck (`[AMI: unverifiable]`, the `_annotate_rr_against_levels` pattern at
`room_runner.py:2359-2373`) or dropped from the headline slot while surviving in
the body. Cheapest real win in this audit.

### F3 — Stance-envelope `HEADLINE:` may carry an unverified number

**What.** Free text up to `STANCE_HEADLINE_MAX_CHARS`, nulled if over
(`room_runner.py:3203-3206`). No numeric constraint.

**Where it lands.** The comb hex headline — high-visibility, low-context, the
string a user reads *instead of* the turn.

**Worst plausible error.** A headline asserts a figure ("EPS down 40%") that the
turn's own prose contradicts or that the sheet does not support. The user reads
only the headline.

**Fix class.** *Check-and-rewrite* — same checker as F1/F2, applied to the
headline string before it is stored on the `AgentMessage`
(`room_runner.py:5404-5407`). Or *strip*: null a headline containing a numeral
the sheet cannot corroborate, reusing the existing null-don't-cut rule.

### F4 — `time_horizon_days` is unbounded

**What.** `int(parsed.get("horizon_days"))` with a fallback, and no range check
(`room_runner.py:2010-2012`). The grammar is a bare nullable integer
(`room_prompts.py:617`).

**Where it lands.** The verdict card's horizon field; the Journal board
(`room_board_mappers.dart:135`).

**Worst plausible error.** A 3,650-day horizon on a swing trade, or a 1-day
horizon on a thesis trade. Partially mitigated — `_horizon_coherence_note`
(`room_runner.py:1605`) already flags a horizon the stop cannot serve, and it is
appended to `reason` at `room_runner.py:2046`. But that note is prose beside the
number, and the *field* still renders the implausible value.

**Fix class.** *Check-and-rewrite* — a plausibility band (mirroring
`_level_is_implausible` at `room_runner.py:2750`), clamped-and-disclosed the way
`size_pct` is clamped at `room_runner.py:2023-2025`. Low harm, near-zero cost;
worth doing in the same pass as the guard because it is the one *card field*
with no bound at all.

### F5 — The 1-on-1 surface has no numeric verification whatsoever

**What.** No geometry check, no R:R rewrite, no direction check, no sheet
comparison. See §2.4 for the negative evidence.

**Where it lands.** The full 1-on-1 chat transcript.

**Worst plausible error.** An agent states a level triple with an incoherent R:R
in a 1-on-1 — precisely the thing DEF095 exists to catch in the Room — and it
stands unmarked. The user has no way to know the Room's checks do not extend
here, because the agents, the sheet and the voice are identical.

**Ranked below F1-F3 on *harm*, not on *severity*.** The gap is total, but the
1-on-1 is an explanatory surface, not a decision surface: no position is sized
from it and the safety floor is not in the path, so the blast radius is bad
narration rather than a bad book. It is ranked here on that basis alone, and the
ranking should be revisited if 1-on-1 output ever feeds a trade ticket.

**Fix class.** *Check-and-rewrite* — `_verify_and_annotate_geometry` is already a
pure function of `(text, size_pct, reference_close)` (`room_runner.py:3269-3274`).
Wiring it into the 1-on-1 response path is a small change with a large coverage
gain, and it is the single highest coverage-per-line item in this audit.

### F6 — `kill_criterion` may assert an unverifiable threshold

**What.** Free text, length-bounded only. The schema comment is candid that the
sheet-quantity property is asked for and scored, not enforced
(`schemas/room.py:99-104`); the grammar rationale explains why a grammar was
deliberately *not* used (`room_prompts.py:625-634`).

**Where it lands.** The verdict card, as the most teachable line on it.

**Worst plausible error.** A criterion naming a quantity the sheet does not carry
("if free cash flow turns negative" when FCF is not on the sheet) — a
falsification test the user can never actually run, which reads as rigour while
being unfalsifiable.

**Fix class.** *Check-and-rewrite* — vocabulary check against the sheet's own
field names (WP02 R11's rule), annotating rather than stripping. Note this is
already a **known, deliberately-deferred** decision, not a discovery; it is
listed for completeness of the inventory. Low harm.

### F7 — RO `recommended` and `confidence` (noted, not a finding)

Both are LLM-stated but code-validated: `recommended` renders only on a matching
rung (`risk_officer.py:370-377`), `confidence` only on an enum hit
(`risk_officer.py:367-369`). Listed so the guard's registry has a row for them,
not because they need a fix.

---

## 4. R20 coverage check — §13(a) per-rung dollar risk

**Verdict: §13(a) remains OPEN. R20's shipped precompute does not cover it.**

`LadderOption` carries exactly five numerics —
`trading_math/option_ladder.py:39-48`:

```
label, size_pct, contribution_pts, share_of_cap_pct, headroom_after_pts, reward_risk
```

**All of them are percentages, points or ratios. There is no dollar figure and
no portfolio value on the rung.** `build_option_ladder`
(`trading_math/option_ladder.py:63-72`) does not take `portfolio_value` as a
parameter at all, so a per-rung dollar risk is not merely absent from the output
— it is not computable from the function's inputs.

Confirming from the render side: `_rung_head`
(`risk_officer.py:318-328`) prints only `size_pct`, `contribution_pts` and
`headroom_after_pts`, and its docstring is explicit that these are "ladder values
only, so no formatter exists that could render a payload number."

**Where dollar risk *does* exist, and why it does not satisfy §13(a):**

- `room_runner.py:1337` — `budget = round(portfolio_value * contribution.contribution_pts / 100.0, 2)`.
  This is the real per-trade dollar risk and it is computed correctly. But it is
  computed for **one** size (the Trader's proposed `size_pct`), it is consumed as
  `max_loss_budget_usd` by the *option* strategist (`room_runner.py:1369`), and it
  is **gated on `derivatives_allowed`** (`room_runner.py:1323-1324`) — so on an
  equity run it is never computed at all. It never reaches the ladder and never
  reaches the user.
- `room_prompts.py:2024` — `dollars = portfolio_value * cap_pct / 100.0` in
  `_cap_in_shares_clause`. This is the *cap* in dollars, one figure for the whole
  mandate, not per-rung, and it is position size rather than risk.

So the exact §13(a) ask — *per-rung dollar risk on current portfolio value, so no
agent ever multiplies* — is unbuilt. The arithmetic is `portfolio_value *
contribution_pts / 100`, which is the identical expression already at
`room_runner.py:1337`; the work is threading `portfolio_value` into
`build_option_ladder`, adding the field to `LadderOption`, and rendering it in
`_rung_head`.

**One caution for whoever builds it.** `build_option_ladder`'s existing
discipline is that a figure it cannot honestly compute stays `None` rather than
assuming a default — stated at `trading_math/option_ladder.py:79-83`, and the
`headroom_after_pts` guard at `option_ladder.py:101-105` is the working example.
A dollar risk against a missing or zero `portfolio_value` must follow that rule
and render nothing, not `$0`. `_cap_in_shares_clause` already makes exactly this
call at `room_prompts.py:2021-2022`, for exactly this reason.

---

## 5. Phase-2 guard design sketch

**Not built. Sketch only**, per the WP.

### The pattern

R13's exhaustive-guard shape, applied to numerics: **every numeric the user can
read declares its provenance class in a registry, and a numeric that reaches a
render site without a registry row fails the build red.** The value is not in
classifying today's fields — this document does that — but in making tomorrow's
*new* field impossible to add silently. That is the DEF038/DEF063 lesson from
CLAUDE.md's degrade-loudly rule, one domain over: a field that ships undeclared
is a field nobody decided about.

### Registry shape

One row per user-visible numeric, keyed by surface and field:

```python
NUMERIC_PROVENANCE: dict[tuple[str, str], Provenance] = {
    ("verdict", "size_pct"):     Provenance.CODE_CHECKED,
    ("verdict", "entry"):        Provenance.CODE_CHECKED,
    ("verdict", "stop"):         Provenance.COMPUTED,
    ("verdict", "time_horizon_days"): Provenance.LLM_UNVERIFIED,  # F4
    ("risk_rung", "contribution_pts"): Provenance.COMPUTED,
    ("risk_rung", "key_number"): Provenance.LLM_UNVERIFIED,       # F2
    ...
}
```

`Provenance` is a three-value enum matching this audit's classes. A row carries
the checking/computing site as a string so the registry is self-documenting and
the citation cannot rot silently.

### The three enforcing checks

1. **Exhaustiveness over the schema (the red-fail).** A test walks
   `Verdict.model_fields` and `CostedStructure.model_fields`, selects every field
   whose annotation is numeric (or a container of numerics), and asserts each has
   a registry row. **A new numeric field on the verdict card fails the build until
   someone classifies it.** This is the whole point of the guard and the only part
   that must be exact.

2. **No silent downgrade.** A row may not move from `COMPUTED` or `CODE_CHECKED`
   to `LLM_UNVERIFIED` without the test being edited in the same commit — i.e. the
   registry is the thing a reviewer reads to see a guarantee being given up. This
   is the `test_config_compose_parity.py` idea (a declared thing must stay
   declared), not a new mechanism.

3. **Declared-checker-exists.** Every `CODE_CHECKED` row names a callable, and
   the test asserts that callable is imported and reachable from the render path.
   This is what would have caught DEF288's shape — an annotation claiming a
   rewrite happened when the rewriter had matched nothing.

### What the guard deliberately does not do

- **It does not check prose.** F1, F3 and F5 are prose-surface findings and a
  field registry cannot reach them; they need the checker proposed in F1. Saying
  so explicitly matters, because a green registry could otherwise be read as "every
  number is verified", which would be the CR040 failure this whole CR is chasing —
  a control that reports a guarantee it does not provide.
- **It does not veto.** Consistent with DEF059: `enforce_safety_floor` is the sole
  vetoer. The guard is a build-time check, not a runtime one.
- **It does not enforce correctness**, only *declaration*. A row saying
  `LLM_UNVERIFIED` is a passing row. The guard's job is that the class is a
  decision on the record, not an accident.

### Suggested phase-2 sequencing

| Order | Item | Why |
|---|---|---|
| 1 | F5 (wire the geometry check into 1-on-1) | Largest coverage gain per line; the function is already pure |
| 2 | F2 (`key_number` check-or-strike) | Closes the one hole in CR197's structural claim; headline slot |
| 3 | The registry guard | Freezes the classification before more fields land |
| 4 | F4 (horizon band) | Trivial, and it is the last unbounded card field |
| 5 | F1 (sheet-figure checker) | Highest harm, largest build; do it with the harness in place so it can be measured |
| 6 | §13(a) per-rung dollar risk | Independent of the above; small |
| — | F3, F6 | Fold into F1's checker; neither justifies its own pass |

---

## 6. Citation spot-check note

Every `file:line` above was opened and read in this pass, not grepped and
assumed. Three of the negative claims are the ones most worth re-checking,
because a negative is the easiest thing to get wrong:

- **F5's "no verification in 1-on-1"** — established by grepping the entire
  241-line `backend/app/api/one_on_one.py` for `annotate`, `geometry`,
  `risk_reward`, `trading_math`, `verify`, `_match_level` and `room_runner`. The
  only hit is a comment at line 200. There is no service-layer file for this
  surface (`find backend -name "*one_on_one*"` returns the schema, the API and
  tests only), so there is no second place for the check to hide.
- **§13(a) not covered** — established from `LadderOption`'s field list
  (`option_ladder.py:39-48`) and `build_option_ladder`'s signature
  (`option_ladder.py:63-72`), which does not accept `portfolio_value`.
- **F1's gate** — `room_runner.py:3304-3305` is the early return that makes every
  non-triple prose numeral unreachable by the only prose checker in the Room.
