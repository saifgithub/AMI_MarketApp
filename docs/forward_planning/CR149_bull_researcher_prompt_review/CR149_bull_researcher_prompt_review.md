# CR149 — Bull Researcher: the sizing number is a function of the cap, and nothing checks the arithmetic

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence rather than bundled.

**Source:** CR143 Phase 1/3b plus two independent reviews of this agent — a blind prompt-coherence
audit ([`external_review/room/bull_researcher.md`](../CR143_agent_prompt_audit/external_review/room/bull_researcher.md))
and a codebase-verified data-sufficiency audit ([`external_review/room/kimi/bull_researcher_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/bull_researcher_data_sufficiency.md)).
Both processed as **hypotheses**. Every claim was put through a supplier check (does the code inject
the data the prompt claims?) and a parser check (does anything read the output this instruction
shapes?) before becoming scope — CR105 Amendment 1 is the precedent: written from prompt files alone,
2 of its 4 findings were wrong once checked against the parser, and its "fix" would have turned an
existing guard red.

**Corpus:** `CR143_agent_prompt_audit/corpus/room_runs_2026-08-07-epoch.json` (18 convenes) and
`llm_audit_2026-08-07-epoch.json` (216 turns, each with its verbatim `system_prompt`), plus
`backend/tests/unit/fixtures/pm_verdict_corpus.txt` (811 deduplicated real PM verdict `reason`
strings carrying a `$`). Every rate below is **n=18 Bull turns, epoch 2026-08-07**, unless stated.
Production functions were imported and replayed over the real replies rather than reasoned about.

---

## Why

The Bull is the **best-supplied agent in the Room**. That part of the data-sufficiency review holds
on the supplier check: the four-analyst transcript is complete in **18/18** turns (RESEARCHERS run
sequentially after ANALYSTS commits, `room_runner.py:157`), the enforced single-name cap is the same
`resolved_single_name_cap_pct` the safety floor clamps to (`room_prompts.py:422`), and the Decision
Journal is real (`journal_context.py` — ticker-scoped, plan-gated, ≤5 entries; present in 3/18
convenes, absent in the other 15 because those users have no history for that ticker).

The problem is not supply. It is that **the three most specific things this prompt asks for are the
three it does not get, and the one number it does produce is unverified.**

### 1. The output-style block is inert

`content/agents/bull_researcher.md` ships four numbered demands in **18/18** prompts. Measured:

| instruction | source | delivered |
|---|---|---|
| *"Cite 3–5 specific analyst points as evidence"* | `bull_researcher.md:26` | **1/18** turns name ≥3 analysts; **14/18 name none at all** |
| *"Lead with the thesis in one paragraph"* | `:25` | **3/18** (15/18 use bullets — the later `_PROSE_FORMAT` wins) |
| *"…thesis + evidence + **falsifier**"* | `_LENGTH_GUIDE`, `room_prompts.py:72` | **0/18** — no turn states an invalidation condition |
| *"End with a sizing suggestion based on conviction × user's risk tolerance"* | `:28` | 16/18 state a size; the *"conviction ×"* half does nothing — see §3 |

The falsifier is the sharpest of these: it is demanded in every prompt, it is **derivable from data
already on the sheet** (the 50-day and 52-week lows, PEG, margin), and it is delivered zero times in
eighteen. It is also demanded in only one place — `_LENGTH_GUIDE` — while `bull_researcher.md` never
mentions it. Same split CR150 found on the Bear's "invalidator".

### 2. Nothing reads a Bull turn except the stance envelope

The parser check is unambiguous. Replaying the production functions over all 18 replies:

- `_verify_and_annotate_geometry` runs on **every** prose agent (`room_runner.py:3526`), but it needs
  a full entry+stop+target triple. The Bull states one **0/18** times, so it never fires.
- `_LEVEL_PATTERNS` therefore never matches; DEF235 is a Trader-shaped problem, not a Bull one.
- `_direction_contradictions` / `_annotate_direction_against_price` are wired **PM-only**
  (`room_runner.py:3299`), inside `_parse_pm_verdict`'s post-processing.
- `parse_stance_envelope` is the **only** machine read of a Bull turn. Stance parsed 18/18 (`for`
  18/18, conviction `high` 10 / `medium` 8, never `low`).

So every number the Bull states — the upside percentage, the position size, the drawdown arithmetic —
enters the transcript, the app, and the Journal **unchecked**. And it travels: **32 of 811 (3.9%)**
real PM verdict `reason` strings name the Bull, two of them quoting a Bull figure back as the
justification of record (*"The Bull's 2% sizing aligns with the long-horizon wealth mandate…"*).

The arithmetic is not reliably right. Of the **11** stated upside percentages, recomputed against
that convene's own `Reference price` and `Analyst consensus target`:

| ticker | stated | true | error |
|---|---|---|---|
| GRAB | 44% | **60.49%** ($3.67 → $5.89) | **−16.5 pt** |
| AMD | 30% | **26.65%** ($480.23 → $608.23) | **+3.4 pt** |
| the other 9 | — | — | ≤0.4 pt |

**2 of 11 (18%) are materially wrong.** Both inputs are on the same page of the same prompt; both
outputs are the headline claim of the turn. This is DEF237's shape (no plausibility backstop) on a
different quantity — DEF237 covers entry/stop/target, which this agent never states.

### 3. The cap is the sizing model — and 7 of 18 mandates have no cap

*"conviction × user's risk tolerance"* has no scale behind it. Nothing in `trading_math/sizing.py`
maps conviction to a fraction; the only number the prompt hands over is the CR055 ceiling. So the
ceiling becomes the model. Sizes re-derived **per convene against that convene's own cap** (the same
ticker appears twice with different caps — pooling them is how a sibling CR got a figure wrong):

| cap in force | n | sizes proposed |
|---|---|---|
| **3.0%** | 10 | 3.0 ×6, 2.0 ×2, 1.5 ×1, none ×1 |
| **10.0%** | 1 | 10.0 |
| **100.0%** | 7 | 50, 30, 7, ~6, none ×3 |

Where the cap binds (11 convenes), **all 5 `CONVICTION: high` turns that stated a size went to 100%
of the cap**; the 3 that came in under it were all `medium`. That is not conviction pricing risk —
that is conviction toggling between "the ceiling" and "a bit under the ceiling".

Where the cap does **not** bind — **7 of 18 epoch mandates carry an explicit
`single_name_cap_pct = 100.0`**, and `resolved_single_name_cap_pct` returns an override verbatim
(`sizing.py:73-84`; CR129/DEF187 removed `SINGLE_NAME_ABSOLUTE_CAP_PCT`'s 50% fallback from
`safety_floor.single_name_cap_pct`, so 100.0 is genuinely what is enforced) — the Bull produced 6%,
7%, 30% and **50% of the portfolio in a single name**, with nothing anchoring the choice.

The 50% turn is the worst thing this CR found, and it is user-visible:

> **Sizing Suggestion**: Given the **3/5** risk tolerance and the clear numerical gap between current
> price and target, allocate **50%** of portfolio capital to this single name. This respects the
> **100%** single-name cap while balancing the **50%** portfolio drawdown limit; a move to **$41.0**
> would trigger a **66%** loss on this position, resulting in a **33%** portfolio drawdown
> (50% size × 66% loss / 100), which stays within the **50%** portfolio-level safety floor.
> — SNDK, 2026-08-07

The formula is the one the prompt teaches (`_drawdown_snapshot_line`, in 18/18 Bull prompts). The
inputs are not: the reference price in that same prompt is **$1,212.21**, so a move to the $41.00 the
turn names is **−96.6%**, not −66%. The true contribution is **48.3 pt against a 50% cap**, not
33 pt. A 15-point understatement, in AMI's own taught arithmetic, closing on the words *"stays within
the … safety floor"*. Nothing in the pipeline recomputes it.

### 4. The baked-in literal does NOT leak here — and that is a finding, not an absence

CR150 found `bear_researcher.md:27`'s worked example (*"if X happens, we're looking at −25%"*) three
lines above the grounding directive, and `-25%` turned out to be the single most frequent downside
magnitude in the 811-row verdict corpus (22 verdicts, 12 attributing it to the Bear). The Bull
carries the same *shape* — `bull_researcher.md:26`, *"(e.g., 'Fundamentals Analyst flagged 32% gross
margins…')"*, a literal number inside an example, in 18/18 prompts. Both external reviews recommended
cutting it for the same reason.

Measured the same way: **`"gross margin"` appears in 0 of 216 epoch turns and 0 of 811 PM verdict
rows.** `32%` appears in one Bull reply — it is the real Reddit bullish split from that convene's
fact sheet — and in 3 verdict rows, all unrelated derived figures. **Zero leakage.**

The mechanism explains the asymmetry and is worth keeping: the Bear's example fills a slot the data
*cannot* fill (a downside magnitude — no volatility, no beta, no scenario impact exists anywhere), so
the model reaches for the nearest number, which is the example's. The Bull's example decorates an
*attribution pattern* whose slot the transcript already fills four times over — and which the model
ignores in 14/18 turns anyway. **An example only leaks into the slot its instruction cannot otherwise
fill.** That is the guard-worthy generalisation, and it is why the Bull's `32%` is a tidiness item
and the Bear's `-25%` was a defect.

---

## Scope — four tiers, ordered by cost

### Tier A — prompt-only, free, ships alone

All four are edits to `content/agents/bull_researcher.md` and the two lines that shape it. No
provider, no fetch, no parser surface.

1. **Rewrite the citation instruction to something the model does.** *"Cite 3–5 specific analyst
   points"* is at 14/18 zero-compliance. The transcript is complete in 18/18 and the Bull plainly
   *uses* it — it just does not attribute. Ask for what is enforceable: *name the analyst whose
   contribution each piece of evidence comes from*. The `32% gross margins` example goes with the
   rewrite — **not because it leaks** (§4: it does not), but because a worked example for a dead
   instruction is dead weight, and because the number it models is one `_format_profile` cannot
   supply on any sheet.
2. **Resolve `:25` against the format contract.** *"Lead with the thesis in one paragraph"* loses to
   `_PROSE_FORMAT`'s *"one-sentence thesis, then short bullet points"* 15 times in 18. Make the base
   file say what the system actually asks for. (This is the Bull's own line, not DEF236's shared
   `_LENGTH_GUIDE`/`_PROSE_FORMAT`/`_STANCE_FORMAT` triangle — that stays CR145's.)
3. **Put the falsifier in one place, and make it a slot.** It is demanded only by `_LENGTH_GUIDE` and
   delivered 0/18. Either the base file asks for it as a named element ("state the level or figure
   that would break this thesis, from the block above") or it comes out of the length guide. It must
   not be asked for in exactly one place and measured at zero.
4. **Two one-line disclosures, both cheap, both with measured harm near zero — take them, don't sell
   them:**
   - *"consensus target carries no stated horizon"* in the fact sheet. Supplier check confirms the
     gap: `targetMeanPrice` (`fundamentals.py:277-279`) carries no date and yfinance exposes no
     target horizon anywhere we read. Measured consequence today: **2/18** turns invent the linkage
     (AMD *"$608.23 by 2026-11-03"*, AVGO *"$527.88 by 2026-09-02"*), both to the earnings date.
   - *"Ticker blocklist: (none declared)"*. `overlay_generator.py:358` emits *"Respect
     ticker_blocklist absolutely"* in 18/18 Bull prompts while `:143-144` renders the list only when
     non-empty — **0 of 216 epoch prompts** carry one, so the agent cannot distinguish "empty" from
     "not attached". Measured consequence: **0/18** replies mention a blocklist. Cosmetic, one line.

### Tier B — the sizing model (the substantive work; needs a decision before code)

A conviction→size policy that routes through `resolved_single_name_cap_pct`, so the narrated fraction
and the enforced clamp cannot diverge — the CR046/CR055 shown==enforced invariant. Without it the
ceiling is the only signal in the prompt and the model uses it as one.

The harder half is not the Bull's: **7 of 18 epoch mandates set `single_name_cap_pct = 100.0`.** For
those runs the CR055 cap note is a no-op, `SINGLE_NAME_ABSOLUTE_CAP_PCT`'s 50% is not in the path
(CR129/DEF187 removed it as the floor's fallback), and a 50%-of-portfolio suggestion is not clamped
by anything. Whether a 100% single-name cap should be reachable at all is a **mandate/policy
decision for Saiful**, not a prompt fix — but the Bull is where it becomes a sentence a user reads,
and it should be decided in the same breath as the conviction table.

Also in this tier, cheap and cross-agent: **render the stance on transcript entries.**
`_format_transcript` (`room_prompts.py:886-892`) emits `[agent_id] content`, and
`parse_stance_envelope` has already stripped the envelope before the commit (`room_runner.py:3496`),
so the Bull reads four analyst turns with no conviction signal — it cannot weigh whom to cite.
`AgentMessage` already carries `stance`/`conviction` structurally (CR106 B2), so this is a render
change of ~15 chars per transcript line, and it lands on every sequential agent.

### Tier C — a derived-arithmetic backstop (extends DEF237's shape)

Both classes of error measured above are recomputable from data AMI already holds at render time:

- **Upside %** — `Reference price` and `analyst_target_price` are both in the profile dict. A
  narrated upside that disagrees with `(target − ref)/ref` by more than a tolerance gets AMI's figure
  appended, in the established `[AMI: …]` voice (`_annotate_rr_against_levels` is the pattern; the
  `[AMI` prefix is already the client's amber-mark test, CR106 §3.3). Would have caught GRAB's
  16.5-point error and AMD's 3.4-point one.
- **Drawdown contribution** — `drawdown_contribution` already exists in `trading_math`. A turn that
  narrates *"P% size × S% loss / 100"* against a price it also names can have S recomputed against
  the run's reference price. Would have caught SNDK's 15-point understatement.

Flag-only, never a veto (DEF059 — the safety floor stays the sole vetoer). Note this is **adjacent to
DEF237, not covered by it**: DEF237 is a plausibility backstop on entry/stop/target, and the Bull
states a full triple 0/18 times. The exposure is on a different quantity, and it is the one that
reaches the PM's verdict text.

### Tier D — not scoped

A real consensus-target horizon needs a new provider (TipRanks/Zacks-class). Out of scope for a
prompt-audit CR; Tier A's disclosure is the correct cheap answer and closes the measured failure
mode without pretending to data we do not have.

**Explicitly NOT re-litigated** (owned by CR145): the `_LENGTH_GUIDE`/`_PROSE_FORMAT`/`_STANCE_FORMAT`
conflict (DEF236), `LearningStyle.QUICK`'s *"tabular"* against *"no tables"*, and the per-agent fact
sheet (`_format_profile` takes no `agent_id`). Already filed: DEF235 (the `size` prose-parse — fixed,
size now comes from the mandate cap) and DEF237 (the missing plausibility backstop — open).
Already claimed by CR150 on the shared mandate block, measured identically here and **not
duplicated**: market cap absent 0/18 while *"avoid microcaps (< $500M market cap)"* renders 17/18;
`Total open-risk cap` stated 18/18 with the current open risk rendered 0/18.

---

## Acceptance

- **Tier A:** no instruction in `bull_researcher.md` demands a number `_format_profile` cannot supply;
  the falsifier is asked for in exactly one place; the thesis-format line agrees with `_PROSE_FORMAT`;
  the undated-target and empty-blocklist lines render. Re-measured post-promotion on ≥30 convenes:
  **named-analyst citation ≥3 rises from 1/18**, **falsifier from 0/18**, **invented target-date
  linkage stays ≤2/18**.
- **Tier B:** the size a Bull turn proposes is no longer a deterministic function of the cap — the
  correlation between `CONVICTION` and fraction-of-cap is re-measured and the 5/5-high-turns-at-100%-
  of-cap result does not reproduce. Any conviction table reads the same `resolved_single_name_cap_pct`
  the floor enforces; a divergence test fails the build. The 100%-cap question has a written decision.
- **Tier C:** replay the annotator over the committed epoch corpus before shipping — it must flag
  GRAB (44 vs 60.49) and SNDK (33 pt vs 48.3 pt) and must **not** flag the 9 correct upside figures.
  Post-promotion, the materially-wrong-derived-figure rate falls from 2/11.
- **Every prompt edit is re-measured after promotion against CR143's baselines.** A prompt edit whose
  effect is not re-measured is the CR105 Amendment-1 trap.
- `pytest backend/tests/unit/ -q` green throughout.

---

## Rejected — with the evidence that killed each

This is the part worth reading. Nine claims arrived; six did not survive.

1. **"Cut the `32% gross margins` example — it trains hallucination of a number not in the data"**
   (blind review §5, endorsed by the data-sufficiency review §6.4 and §7). **Killed on measurement.**
   `"gross margin"`: **0 of 216** epoch turns, **0 of 811** PM verdict rows. The example is still
   removed in Tier A, but as part of rewriting a dead instruction — the stated reason was wrong, and
   recording that matters because the identical shape *did* leak for the Bear (CR150).
2. **"Hallucinated analyst attributions" — blind failure mode #1.** **Killed.** Seven named citations
   across 18 turns; all seven trace to the named analyst's own turn in that convene. The one apparent
   miss (NVDA, *"The Fundamentals Analyst flags … $40.358B in net cash"*) is **verbatim** from that
   convene's Fundamentals turn — an artifact of a first-pass regex that matched the *other* NVDA
   convene's transcript. The real defect is the opposite of the predicted one: the Bull does not
   over-attribute, it **under-attributes**, naming no analyst in 14/18 turns.
3. **"Unfollowable: no analyst outputs provided"** (blind §3). **Killed.** 0/18 empty transcripts;
   RESEARCHERS is a sequential phase after ANALYSTS commits. The blind review's sample showed the
   `(You are first to speak.)` sentinel — a real state, but not one this agent reaches in a full
   roster.
4. **"Wrong or absent STANCE" — blind failure mode #2.** **Killed.** `STANCE: for` 18/18, envelope
   parsed 18/18, conviction never `low`.
5. **"The reply defaulted to the maximum — the cap note failed"** (data-sufficiency gap #1, drawn
   from n=1). **Rescoped, not killed.** At-cap in 7 of the 10 sized turns under a binding cap; 3 came
   in below. The accurate statement is narrower and more damning: *every* high-conviction turn under
   a binding cap went to the ceiling (5/5), and where the cap is 100% the number is unbounded. "It
   always maxes out" would have been easy to disprove and would have discredited a real finding.
6. **"22.9% is an arithmetic slip"** (data-sufficiency §8). **Correct but trivial, and it masked the
   real ones.** (608.23 − 494.31)/494.31 = 23.05%, so the error is 0.15 pt. Reading one sample found
   the smallest of the three arithmetic errors in the corpus and missed a 16.5-point one.
7. **"Analyst STANCE tails absent from all four transcript entries; adherence is model-dependent"**
   (data-sufficiency gap #5 and §7). **Killed on the supplier check — the mechanism is the opposite.**
   All four analysts emit the envelope in **18/18** turns each. `parse_stance_envelope` **strips it
   by design** at `room_runner.py:3496`, before the transcript commit, so no downstream agent reads a
   machine channel as argument (DEF095). It is not an adherence gap; it is a render gap, and the
   stance is already on `AgentMessage` waiting to be rendered — which is why it is cheap Tier B work
   rather than a prompt problem.
8. **"Highest novel-number rate of any agent (7.5%)"** — **this CR's own stub, corrected.**
   Re-derived over the epoch corpus: **6.2%** (29/467) counting the stance line, **6.1%** (27/443) on
   the body the user reads — and **second**, behind `neutral_debator` at 7.7%. More importantly, the
   rate was read without being read (the P16 mistake). Hand-reading all 27: **~11 are correct
   arithmetic on prompt numbers** (upside %, $941.12 = 10.0% × $9,411.21, MU's $632.61 =
   $1,507.79 − $875.18), **5 are the Bull's own chosen position size**, **4 are unit restatements or
   roundings of prompt figures** ($40358M → $40.358B, $0.20709 → $0.207, $134.0 → $134, the portfolio
   block's "Cash: $10,000.00" → $10,000), and **0 are recalled company facts**. The metric is measuring
   derived arithmetic, not hallucination — which is exactly why **arithmetic accuracy**, not
   novelty, is the number this CR is built on.
9. **"Assembled prompt size 12,640 chars"** — **stub figure, corrected.** That is the single AMD
   sample. Corpus: **median 11,679**, range 11,059–13,402 (n=18).

## Could not verify

- **Whether the seven `single_name_cap_pct = 100.0` mandates belong to real alpha users or to a
  seeded/benchmark account.** Neither corpus file carries a `user_id`, and this session did not query
  Alpha Postgres. It changes the urgency of Tier B's policy half, not its correctness.
- **Whether 2/11 is the true rate of materially wrong upside arithmetic.** Eleven claims is too few
  to distinguish a rate from two accidents. Tier C's acceptance is written to re-measure it, and a
  tolerance tuned against its own two motivating examples would be P16 again.
- **Whether the citation instruction would be followed if the example were removed.** Confounded:
  the one turn that met it (AMD, 3 analysts named) is the sample both reviews read.
- **Journal utilisation.** 3/18 prompts carried history; 1 of those 3 referenced it (the AMD
  Bear-counter bullet). n=3 supports no rate. What *is* clean: **0 of the 15** history-free turns
  invented a past decision — the grounding directive holds on this input.
