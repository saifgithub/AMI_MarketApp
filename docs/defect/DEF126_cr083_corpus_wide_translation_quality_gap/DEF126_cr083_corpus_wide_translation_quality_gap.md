# DEF126 — Corpus-wide AR/MS lesson-translation quality gap

## What

Folding Falcon-H1-34B-GPTQ into the CR083 verification pipeline as a second always-on
model (alongside `primary`/ami-llm) and running it across the full 342-lesson corpus
(684 lesson×locale combos) surfaced a much larger finding than any prior CR083 staleness
wave (DEF097/DEF102/DEF109): **the majority of existing AR/MS lesson translations have
at least one flagged meaning-level defect**, not just staleness against a specific
content-fix commit.

## Measured result (full corpus, not a sample)

- **81 verified** — both `primary` and `falcon` agree, confidence ≥4/5, zero critical
  issues.
- **600 need review** — ≥1 critical issue flagged by `primary` and/or `falcon`.
- **3 permanently unresolved by `falcon`** — a reproducible `falcon` JSON-formatting bug
  (see Process note). `primary` alone has checked these three; they're not "unchecked,"
  just capped below the 2-model bar until the bug is worked around.
- By locale: **AR 293/342 flagged (85.7%)**, **MS 304/342 flagged (88.9%)**.
- Severity distribution (max critical-issue count per lesson×locale, across whichever
  model flagged more): 87 have zero, 242 have 1-2, 295 have 3-5, 60 have 6 or more.

## How found

Explicit user directive this session: "fold in falcon and start using it" (approving a
candidate verifier already evaluated as clearly better than allam/JAIS at catching real
meaning-inverting errors). Wired `falcon` into `scripts/i18n_verify_lesson_translation.py`'s
`ENDPOINTS` dict and ran a corpus-wide `primary`+`falcon` pass (`allam` was unreachable for
the entire run — the script previously crashed the whole batch on one dead endpoint; hardened
it to skip unreachable endpoints with a warning instead). 1,006 fresh checks + a gap-sweep
recovered 4 of 7 checks lost to transient double-failures (retry-then-skip design).

## Is this verifier noise or real?

Spot-checked across the severity distribution (low, medium, and the three most extreme
outliers) before concluding this is a real finding:

- **Genuine, material defects** (representative sample):
  - `014_position_sizing_basics` (ms): the literal English word **"whatever"** left
    untranslated inside Arabic prose (`حجم المركز هو whatever يعطيك إياه الحساب`).
  - `019_survival_mindset` (ar): "protect tomorrow's seat at **the table**" translated as
    "protect your seat at **lunch**" (`الغداء`) — the opportunity/participation metaphor
    is gone, replaced with a literal, nonsensical meal reference.
  - `012_why_most_traders_fail` (ms): "**safety floor**" → literal "lantai keselamatan"
    (physical floor); "**uncoachable**" → "cannot be taught" instead of "cannot be
    overridden by coaching/emotion" — both are safety-floor-adjacent product terms where
    the mistranslation changes the actual meaning of a load-bearing app concept.
  - `001_what_is_a_stock` (ms): "**share**" translated as "**lot**" — a lot is a distinct
    Malaysian trading-unit (e.g. 100 shares), not a synonym for a single share; this
    misleads on the scale/nature of the asset being described.
  - `060_bear_markets` (ar): "**mandate**" → "الولاية" (a governance/political-state
    term) instead of an investment-mandate term.
  - `346_capstone_stress_testing_a_strategy_claim` (ar): "**tail risk**" → "مخيل الذيل"
    ("imagination of the tail") instead of "مخاطر الذيل" (tail risk) — a fabricated,
    nonsensical compound.
- **Verifier self-contradiction (the caveat)**: a heuristic scan for the model's own
  hedge-and-reverse language (an issue's text concluding "is correct" / "is fine" /
  "is acceptable" while still being listed as a critical issue) found this pattern in
  ~9% of the 2,018 raw critical_issue entries corpus-wide, and it's concentrated almost
  entirely in 3 outlier lessons (`346`, `060`, `278` — each with 20-34 raw entries, where
  `primary` walked through nearly every technical term one-by-one and second-guessed
  itself on several). Outside those 3, the flagged issues read as straightforward findings,
  not rambling self-negation. **Conclusion: this is a real corpus-wide quality gap, with
  a small, isolated noise problem in a handful of outlier lessons that need a second look
  before their raw critical-issue counts are taken at face value.**

## Scope note — why this isn't auto-remediated

DEF097/DEF102/DEF109 were each a mechanical fix: retranslate a known, bounded list of
lesson ids via the existing `translate_lessons_lan.py --overwrite` tool, then re-verify.
This finding is different in kind and scale — 600 combos across most of the corpus, each
needing an actual content fix (not just a rerun), most likely requiring targeted
re-translation of specific flagged terms/sentences rather than a blind whole-lesson
re-run (which would just reproduce similar errors from the same base model). Given the
scale, this needs Saiful's call on priority and approach before work starts — options
noted for discussion, not decided here:

1. Blind full re-translation of all 600 flagged combos via the existing pipeline, then
   re-verify — cheapest to run, no guarantee of a better outcome since it's largely the
   same underlying translation model.
2. Targeted fix pass: feed each lesson's specific flagged critical_issues back as
   correction instructions to a retranslation call (translate-with-feedback), then
   re-verify — likely much better yield, more engineering to build.
3. Triage by severity first (the 60 lessons with 6+ critical issues, or specific
   safety/product-terminology terms like "safety floor"/"uncoachable"/"mandate" that
   recur across many lessons) rather than treating all 600 as equal priority.
4. Some combination — e.g. fix the recurring cross-lesson terminology errors (safety
   floor, mandate, uncoachable, edge) globally first since those repeat across dozens of
   lessons, then handle lesson-specific one-offs separately.

## Process note — Falcon wiring + a script robustness fix + a known Falcon bug

- Added `falcon` to `ENDPOINTS` in `scripts/i18n_verify_lesson_translation.py`:
  `http://192.168.20.74:8044`, whole-body (no chunking — 32768 ctx gives ~5.5x headroom
  over the corpus's worst-case lesson, measured at 5,759 prompt tokens).
- Hardened endpoint startup: previously, one unreachable endpoint (`_current_model`
  raising unhandled) crashed the entire batch before a single lesson was checked — caught
  live when `allam` (port 8040) was down for this whole run. Now skips unreachable
  endpoints with a `WARNING:` line and continues with whichever are reachable.
- Found, not fixed (too narrow to justify a repair layer): `falcon` occasionally emits a
  minor_issue array element as a quoted phrase followed by unquoted qualifier text
  (`["foo" - this could be a minor issue]` instead of one clean JSON string), breaking
  `json.loads`. Deterministic per input (temperature=0.1), affects exactly 3/684 combos
  in this run (`173_adjusting_comps_for_size_leverage_growth` ms, `181_pb_for_banks_regulatory_book`
  ms, `249_vvix_and_iv_rv_divergence` ar — all on the `falcon` side only, `primary` checks
  for these three succeeded).
- Purged 708 stale confidence-log entries for the 165 DEF109-affected lessons before this
  run (they scored pre-fix content) — per DEF109's own closing note that old entries
  "should not be treated as still valid for the corrected text."

## Open, unresolved by this Defect

- **Remediation scope/approach** — Saiful's call (see options above). Not started.
- **Sharia `strict_review` lessons' ≥3-model bar** (the full 10-lesson `347`-`356` unit,
  corrected below — not 5 as first written here): with `allam` unreachable for this
  entire run, these currently cap at 2 models (`primary`+`falcon`), same as ordinary
  lessons — the elevated bar is not being silently downgraded, it's just unmet. Needs
  `allam` back online (AR-only) or a decision on an alternate 3rd verifier for MS.
- The 3 `falcon`-JSON-bug combos stay capped at single-model (`primary`) coverage unless
  a future pass works around the bug or another model covers them.
- `ami-llm` (port 8000) production-instability episode from earlier this CR — still an
  open question for Saiful, unrelated to this Defect, not actioned.

## Update 2026-07-29 — remediation executed, partial improvement, still open

Saiful's call, given the four options above: **blind re-translation** (cheapest, no
guarantee of a better outcome since it's the same underlying model). Executed exactly
that — `translate_lessons_lan.py --overwrite` against the 296 AR-flagged + 304 MS-flagged
lesson ids (derived from `--summary`'s NEEDS REVIEW output, not guessed), then a full
`primary`+`falcon` re-verify (1,189 fresh checks: 589 AR + 600 MS).

**Result: 81 → 152 verified (+71), 600 → 529 need review (-71), 3 capped unchanged.**
Per locale: AR 79 verified / 261 need review; MS 73 / 268. A real gain, but partial —
**529/600 combos are still flagged.** If Saiful wants a second pass, the terminology-first,
feedback-fix-tooling, and severity-triage options from the original list are all still on
the table and none has been tried yet.

**DEF105's 7-lesson named subset verified clean.** Before folding this update in, grepped
all 11 phantom-Mandate tokens (DEF102's class-A set + the richer-Mandate set:
`cooldown_after_stop_minutes`, `max_sector_exposure_pct`, `max_open_positions`,
`max_trades_per_week`, `total_open_risk_pct`, `max_single_factor_exposure_pct`, plus
`max_position_pct`, `max_risk_per_trade_pct`, `max_single_name_notional_pct`,
`pause_at_drawdown_pct`, `region_allowlist`) across all 14 `.ar.mdx`/`.ms.mdx` files for
`017`/`047`/`050`/`051`/`109`/`204`/`205`. **Zero residuals.** 13/14 were actually
retranslated this pass; `017` MS wasn't flagged but is independently clean.

**Sharia `strict_review` scope correction.** The unit is the full 10-lesson `347`-`356`
Islamic-finance track (`content/i18n/sensitive_keys.json`'s `strict_review` scope), not 5
as this doc first said. None of the 10 show VERIFIED — correct and expected, since
`_is_verified`'s strict path needs 3 models and only 2 are active. The `allam`/3rd-verifier
decision above now gates all 10, not 5.

### Two process findings from mid-remediation — both read by hand, both flagged, neither hidden

**1. The MS batch recreated a deliberately-quarantined file.** `355_how_amis_
halal_flag_maps_to_real_screening.ms.mdx` had been physically deleted from the repo after
an earlier translation attempt inverted its halal-mechanism description (see git history
on that path: `bc02bb13`). The id-list for this remediation was built from `--summary`'s
output, which read a **stale confidence-log entry** from before the quarantine — the log
isn't pruned when a translated file is deleted, so a deleted file can still look like an
ordinary flagged lesson to anything that reads the log rather than the filesystem. The
fresh translation was read in full before being allowed to ride through the commit: it
correctly describes the current four-outcome mechanism (PASS/SCREENED OUT/UNKNOWN/PAUSED),
both quiz answers are correctly keyed to that mechanism, and the SME-escalation disclaimer
("not a fatwa... consult a qualified scholar") is intact. Kept, not reverted — but flagged
to Saiful rather than silently accepted, since Sharia content is exactly the class this
project's own convention says should escalate, not auto-pass.

**2. DEF144's own fix bypassed the sensitive-key exclusion mechanism.** Fixing the
`platform.json` foreign-script leak (DEF144) used an ad-hoc script that called
`translate_content_lan.py`'s internals directly, with no awareness of
`content/i18n/sensitive_keys.json`. That file's `content_json_ids` scope flags exactly one
entry in `platform.json` — `qa_plt_halal_flag`, the halal-filter Q&A — as
Sharia-ruling-adjacent and requiring the stricter bar. The ad-hoc fix retranslated it
along with the other 39 records. Read by hand afterward: matches the current four-outcome
mechanism, no ruling fabrication, disclaimer intact — correct by the luck of careful
review, not by design. **The exclusion mechanism only protects the four standing CLI
tools; an emergency/ad-hoc fix path has no guard at all.** That's a real gap, not a
one-off — flagged here rather than fixed, since building it properly is more than this
defect's scope.

Both findings land on the same point Saiful raised at the start of this remediation:
guardrails built for the planned path don't cover the emergency-fix path, and Sharia
content needs the exclusion check to be structural — checked by the tooling, not
remembered by whoever is driving it.
