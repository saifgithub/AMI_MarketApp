<!-- CR109 review synthesis — the closing pass over the AT:Fable review series. Re-reads
     the psychology and comparative reviews in light of everything decided after them (the
     trading cost, the day-trade rule, the fast ticket, the lab framing) and records ten
     second-order insights the interactions produce — including one that upgrades a
     finding's severity (S2) and two that catch the reviews' own additions creating new
     problems (S3, S4). Then consolidates every insight from the whole series into one
     register, restates the Stage-1 manifest as a single list, and maps all documents
     produced. Design stage; changes nothing by itself. -->

# CR109 — review synthesis

**Closes the AT:Fable review series.** `AT:Fable`, 2026-07-30.

Saiful: *"have another look at psychology review and comparative review. with what we have done,
maybe you have further insight. and finally, document all insights and a list of all documents
produced."*

The second read was worth it: the decisions taken *after* those reviews — the trading cost, the
day-trade rule, the lab framing — interact with the findings in ways the documents could not
have seen when written. Ten second-order insights (§1), one of which upgrades a finding's
severity, and two of which catch **the review's own additions** creating the next problems.

---

## 1. Second-order insights

### S1 · The fee × benchmark scoring = the industry's own lesson, embedded

Players pay trading costs; the benchmark doesn't. So under the default alpha path, **beating the
market means beating it after costs** — which is precisely the real industry's bar, and the
reason most active managers underperform the index. This is not a bug to engineer away; it is
the most valuable accident in the design. Requirements it adds to F2's formula spec: alpha is
measured **net of fees vs the costless price-only benchmark, deliberately**, and the Close says
so — *"the index pays no fees; you beat it anyway"* is the strongest win-line the game can
print, and the losing version is the index-fund lesson at peak attention (L3's second
counterfactual line, sharpened).

### S2 · The fee makes the F1 stipend load-bearing — severity upgrade

F1 found the median player's expected points ≈ 0. **The fee moves that expectation below
zero:** median gross alpha ≈ 0, minus fee drag, means the median player now *slightly
underperforms* the benchmark on the default scoring path — negative points every run, pinned to
the floor forever. The finish stipend upgrades from *recommended* to **required-if-the-fee-
ships**: the stipend and the fee are a pair (the fee prices churn, the stipend pays completion),
and shipping one without the other tilts the median experience negative. Size them together in
§18.

### S3 · The Close is drifting from ceremony to report — the reviews did it

Count what the series has now attached to the Close: rank + career delta, the field reveal,
near-miss lines, a progress marker, best/worst decision (F6), two counterfactual lines (L3), the
agent post-mortem (C5), intent-vs-outcome (L1), the thin-field basis disclosure, and the
re-entry CTA (F4). **Ten blocks on the screen whose entire job is one emotional payoff.** The
peak-end rule that justified the Close forbids what the Close is becoming.

> **Ceremony budget: three beats.** 1 — the result (rank, delta, the curve). 2 — **one** insight
> block, chosen by priority (first close: the duel verdict; blowup: the post-mortem; near-miss:
> the near-miss; otherwise: the counterfactual). 3 — the re-entry CTA. Everything else lives one
> tap deeper in a **full debrief** panel, and permanently on the Record.
> *A ceremony with an appendix — not a report with confetti.*

### S4 · Entry friction creep — the reviews' additions must obey the reviews' findings

Same shape at the other end of the run: the no-rules disclosure (§7), the cost disclosure,
the intent tag (L1), challenge cards (L5), rebuild-last-book, cadence choice. F3's whole
argument was that first-entry choice load kills beginners — and the series has been quietly
re-loading the entry screen. Rule: **entry stays one screen, three taps to entered.** The
disclosure renders full-text on first entry only, then compresses to a chip; the intent tag is
one optional row; challenges hide behind a single "add a challenge" affordance; rebuild-last-
book appears only when a previous book exists.

### S5 · The Record has quietly become the product's second surface

The series has attached to it: career points + titles, run history with forfeit counts, duel
W–L, the PR board (C6), the skill stat (C4), returns-by-style (L2), badges/flair, intent
history (L1). **Eight retention mechanics on a screen that §13.3 lists as one table row**
("does not exist today"). Treat the Record as a first-class slice-3 deliverable with its own
information hierarchy — identity at top (title, skill stat), movement in the middle (points,
PRs, streak), history below (runs, styles, duels). It is the season loop's entire home; it
should be designed like it.

### S6 · Short cadences are the lab; long cadences are the exam

The series accumulated two framings — the exam (CR109 §2: prove you internalised the Room's
teaching) and the lab (playability addendum: go wild, watch what happens). They are not in
tension; **they are the two ends of the cadence axis.** Weekly runs are the lab: cheap, stipend-
carried, where intent tags, challenges and wild themes attach. Quarter/Half/Annual are the exam:
where titles, the plaque and the Awards live. One sentence for the rules surface and the
marketing copy both — and a guide for where every future mechanic should attach.

### S7 · The fee raises the bar on G3

A quote-staleness exploit now has to clear ~20 bps per round trip plus the day-trade budget
(R1). The measurement task stands — an edge bigger than the friction would still be a time
machine — but its priority drops from urgent to due-diligence: the exploit must now be *large*
to be profitable, and large lags are the easy kind to detect.

### S8 · Every anti-spray friction is pro-skill evidence for §15

The chance-vs-skill leg is the one live leg of the gambling test. The fee, R1, queue-first
planning, and one-beat-per-close all reward deliberation over impulse — which is not just good
design, it is **evidence**. When the §15 legal pass runs, compile the frictions into the
argument: the game's mechanics systematically price out impulse play. The lab framing's §1
inversion (the game *falsifies* gambling psychology with the player's own data) belongs in the
same paragraph.

### S9 · Private fields × themes compose — the lab's group mode

C1 (private fields) and L6 (theme/wild arenas) multiply for free: a private field inherits any
theme config, so an office can run its own high-vol month and a class its own discipline
season. Every combination is config, not code — the content calendar writes itself once both
primitives exist. Sequence unchanged (C1 stays Stage 2); recorded so the field schema carries a
`theme` reference from day one.

### S10 · Twelve constants, one module, one table

The series has scattered tunables across five documents. Consolidated, `games_scoring.py` now
owns: the placement curve, cadence weights (gain and loss rows), title thresholds **plus the
new first rung**, the ×0.5 partial-credit factor, the finish stipend, the alpha→points slope
and cap, duel deltas by cadence, the minimum forfeit debit, the fee bps + minimum, R1's counts,
and the escalator N (reserve). **Each a named constant with a loud test; §18's tuning list
should be regenerated from this table** rather than maintained by hand across documents.

---

## 2. The consolidated insight register

Every insight the series produced, one line each. Status is honest: **decided** = Saiful said
so; **accepted** = filed at his yes; **recommended** = mine, his call pending; **reserve** /
**measure** as marked.

| ID | Insight | Status | Cost | Stage |
|---|---|---|---|---|
| F1 | Median player's Record flatlines at zero → finish stipend | recommended → **required with fee (S2)** | S | 1 |
| F2 | Benchmark path has no points formula → define now, asymmetric, capped, net-of-fee (S1) | recommended | S | 1 |
| F3 | First run = auto-duel vs the Index Desk | recommended | XS | 1 |
| F4 | Re-entry CTA on Close/Wind-Up + close→re-entry as the primary metric | recommended | S | 1 |
| F5 | First title rung at ~100 pts (or milestone-gated) | recommended | XS | 1 |
| F6 | Attribution on the daily beat; best/worst decision at Close | recommended | S | 1 |
| F7 | Handle keep-or-reroll · reactions Phase A early · share card in slice 3 | recommended | XS ×3 | 1 |
| F8 | Near-miss framing points up only — never on losses | recommended (fence) | XS | 1 |
| F9 | Duel queue keeps a pairing key for proximity matching later | recommended (note) | XS | 3b schema |
| C1 | Private fields with join code, points-capped | recommended | M | 2 |
| C2 | Bye week for the runs-finished streak | recommended | XS | 1 |
| C3 | Human-scale boards trigger (median field > ~50 → bracket) | recommended (trigger) | 0 | later |
| C4 | Rolling skill stat (trailing alpha/Sharpe) on the Record | recommended | S | 2 |
| C5 | Agent post-mortem on the Close/Wind-Up | recommended | S–M | 1–2 |
| C6 | PR board on the Record — thin-field-proof self-competition | recommended | XS–S | 1 |
| FEE | 10 bps/fill, min 1.00 AMI Cash, game-only, burned, desks pay it | **decided** (sizing → §18) | S | 1 (slice 2) |
| ESC | FPL-style escalator (N cheap fills, then 3×) | reserve (Gate 1) | XS | — |
| R1 | Day-trade limit, PDT-style (3 same-day round trips / 5 days) | recommended | S | 1 (slice 2) |
| R2/R4 | Same-ticker cooldown · overnight hold | reserve (Gate 1 data) | — | — |
| R3 | Daily fill ceiling as silent API rate limit | recommended (ops) | XS | 1 |
| TKT | 3-tap ticket · size chips (25% visual default) · stop/target chips · rebuild-last-book · queue-first UX | **decided** (his ask) | S mobile | 1 (slice 2) |
| G1 | Dividends unmodeled → price-only SPY now; credit dividends before Q/H/Y | recommended | S / M | 1 / pre-6 |
| G2 | Splits unhandled → adjust + flag + state it | recommended | S | 1 (slice 2) |
| G3 | Quote freshness → measure Yahoo lag on melehost | **measure** (bar raised, S7) | task | pre-board |
| L1 | Run intent tag — sanction the wildness | accepted | XS | 1 |
| L2 | Wildness index → returns-by-style on the Record | accepted | S | 1 |
| L3 | Counterfactual Close (held-untouched · just-held-SPY) | accepted | S | 1 |
| L4 | Book heat gauge, live, informational | accepted | XS–S | 1 |
| L5 | Challenge cards — rules as chosen tools, markers not points | accepted | S | 1–2 |
| L6 | Wild arena as theme config · #9 risk-adjusted early | accepted | config | 3 |
| S1 | Beat-the-market-after-costs is the embedded lesson — say it at the Close | new this pass | copy | 1 |
| S2 | Fee + F1 pair: stipend becomes required, size together | new this pass | — | 1 |
| S3 | Close ceremony budget: 3 beats + debrief appendix | new this pass | design rule | 1 |
| S4 | Entry stays one screen, 3 taps — disclosure compresses to a chip | new this pass | design rule | 1 |
| S5 | The Record is a first-class surface — design it like one | new this pass | design pass | 1 |
| S6 | Weekly = lab, long cadences = exam — the attachment rule | new this pass | copy/doctrine | — |
| S7 | Fee raises G3's exploit bar — measurement is due-diligence now | new this pass | — | — |
| S8 | Frictions are §15 skill-leg evidence — compile for the lawyer pass | new this pass | legal note | pre-launch |
| S9 | Private fields inherit theme config — schema carries `theme` from day one | new this pass | schema note | 2 |
| S10 | All twelve scoring constants in `games_scoring.py`, §18 regenerated from it | new this pass | convention | 1 |

Prior-series items endorsed and unchanged: the playability review's eight changes, the final
review's ad/reminder/social fences, and CR109's decided core (the split, fresh capital, TWR,
one-way rule, disclosed desks, auto-matched duels).

---

## 3. Stage 1, consolidated — one list for the architect

The psychological MVP, gathered from four documents into one manifest. Slices 1–3b/3c as
specced in [`implementation_plan.md`](implementation_plan.md), **plus**:

- **Scoring:** finish stipend (F1/S2) · alpha→points formula, net-of-fee, capped (F2/S1) ·
  first title rung (F5) · all constants in `games_scoring.py` (S10)
- **Trade layer:** the fee (slice 2) · R1 day-trade rule · R3 as silent rate limit · split
  handling (G2) · price-only benchmark declared (G1a) · G3 lag measurement on melehost
- **Surfaces:** 3-tap ticket + presets + queue-first UX · first-run-as-duel routing (F3) ·
  re-entry CTA + close→re-entry metric (F4) · Close on the 3-beat budget (S3) · one-screen
  entry (S4) · the Record designed as a surface (S5) with PR board (C6) and returns-by-style
  (L2)
- **Content/mirrors:** daily-beat attribution (F6) · counterfactual lines (L3, inside the S3
  budget) · intent tag (L1) · heat gauge (L4) · near-miss fence (F8)
- **Retention set (from the playability review, unchanged):** rolling fields · re-homed streak
  + bye week (C2) · provisional rank · daily ritual · Rivals · progress markers at slice 3
- **Identity:** handle keep-or-reroll · reactions Phase A · share card in slice 3, armed with
  the benchmark boast (F7)

Deferred by design: slice 4 machinery, monthly+ cadences, C1/C4/C5 (Stage 2), cosmetics,
challenge cards can trail to 3–4 (L5), roadmap modes (Stage 3). Gates as set in
[`psychology_review.md`](psychology_review.md) §6 — targets to be fixed by Saiful **before**
the build.

---

## 4. All documents produced

The CR109 package, in reading order. Five by `AT:Gamer` (the design), five by `AT:Fable` (the
review series).

| # | Document | By | Lines | What it carries |
|---|---|---|---|---|
| 1 | [`CR109.md`](CR109.md) | AT:Gamer | 1,296 | The game design: three-layer model, run lifecycle, trade rules, scoring, rewards, ceremony, edge cases, compliance, phasing |
| 2 | [`implementation_plan.md`](implementation_plan.md) | AT:Gamer | 466 | Schema DDL, API contracts, slices 1–7, fences, lane split, test matrix |
| 3 | [`playability_review.md`](playability_review.md) | AT:Gamer | 240 | Easy to start / addictive / what brings them back; the dead-start fix; eight changes |
| 4 | [`final_review.md`](final_review.md) | AT:Gamer | 203 | Ads (the rewarded-video trap), the reminder rule, social phases A→C |
| 5 | [`games_roadmap.md`](games_roadmap.md) | AT:Gamer | 269 | Fifteen modes beyond MVP, ordered by cost-to-value |
| 6 | [`psychology_review.md`](psychology_review.md) | AT:Fable | 350 | Mechanism inventory · findings F1–F9 · dark-pattern register · three loops · staged funding with gates |
| 7 | [`comparative_review.md`](comparative_review.md) | AT:Fable | 251 | Genre benchmark: 7 validations, 2 anti-models, additions C1–C6 |
| 8 | [`trade_execution_addendum.md`](trade_execution_addendum.md) | AT:Fable | 212 | The fee · simple-rules menu R1–R4 · 3-tap ticket · engine gaps G1–G3 |
| 9 | [`playability_addendum.md`](playability_addendum.md) | AT:Fable | 147 | The lab framing · additions L1–L6 · mirror guardrails |
| 10 | `review_synthesis.md` | AT:Fable | this | Second-order insights S1–S10 · the consolidated register · the Stage-1 manifest · this map |

**Visual companion (Artifact, private):** *CR109 — Psychology Review* —
`https://claude.ai/code/artifact/fbebb42a-4940-459c-9ead-e3e12d71f328` — the whole review series
on one page: verdict, F1 flatline chart, findings, comparator matrix, trade layer, the lab,
funding rail. (The earlier *CR109 screens & app integration* artifact is AT:Gamer's, separate.)

**Commits (all pathspec-clean, docs-only, additive):** `fade09dc` psychology review ·
`3c902a34` comparative review · `ce74fbc0` trade-execution addendum · `cd9999d9` playability
addendum · this file's commit closes the series.

**Fold-in protocol:** each AT:Fable document ends with a "what changes where" list; CR109.md
itself was deliberately never edited, so the design doc keeps one author. When Saiful approves
the package, the next CR109.md revision applies the fold-ins in one pass — §6 of the trade
addendum, §4 of the playability addendum, and §1–§3 of this file are the complete set.
