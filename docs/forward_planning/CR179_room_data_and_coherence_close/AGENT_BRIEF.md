# Agent brief — the Room prompt/data work after CR179

*Written 2026-08-14 (AT:R68) to hand the current state to another agent. Paste or point at this file.
Not a `HANDOVER_*` doc — that mechanism was retired in CR097; this is a one-off briefing.*

---

## Read this first

**CR179 is closed and the Room's prompt/data surface is FROZEN.** `room_prompts.py`,
`content/agents/*` and the four fetchers (`fundamentals.py`, `news_context.py`, `social_context.py`,
`market_data.py`) are frozen. 15 CRs closed with it: CR143, CR145–CR156, CR166, CR179.

The freeze covers **feature churn**, not defect fixes. DEF302 was fixed inside the freeze the same day
it was declared, deliberately and on the record. If you need to touch a frozen file, it must be for a
filed defect, and say so in the commit.

**`main` and Alpha are identical right now** — `alpha-2026-08-14-2` / `c7a39ee7`. Verify before
assuming: `curl -fsS http://192.168.20.59:8000/v1/health`.

**CR160 is now unblocked** (rename 6 agents away from the TradingAgents lineage, 272 files + AR/MS
transcreation). It was held behind CR179 because renaming agents mid-flight would make every
measurement below unreproducible. It is schedulable; it is not started.

---

## The one thing most worth knowing

**A defect was filed in this build off a broken measurement, and it survived review until the fix
required re-reading the source.** DEF302 was originally filed as *"the Trader's stop-distance
percentage is unverified and laundered downstream"*, citing `Stop: $164.70 (-5% below entry)` against
a $203.62 close. That is **correct arithmetic** — the Trader had proposed `Entry: $173.40 (limit buy
at 50-day SMA)`, and 164.70/173.40 = −5.02%. The checker had equated "entry" with "last close".

Two published rates were wrong as a result (12.5% / 13.8%, corrected to 3/40 and 1–2/29), and the
defect named the one agent it least applies to. **Every Trader stop-distance claim in both epochs is
correct.**

This is now **P19** in `docs/initial_specs/08_tech/failure_patterns.md`: *a new measurement contradicts
a control already shipped, and the measurement is believed.* The tell was available the whole time —
`_annotate_rr_against_levels` had printed the correct `5.0% downside` **in the same prompt the checker
was reading**. If you build any prose-measurement script here, read P19 first and run your metric
against whatever shipped control already computes the same quantity.

**CR179 was never audited.** Six per-leg handshakes were required by its own plan
(`orchestration/audit/cr/R68-CR177-LEG<N>.architect.md`); zero were submitted. `orchestration/audit/cr/`
has no CR179 or CR177 entry. The build is live on Alpha unaudited. That is the largest open risk in
this area and it is not waived.

---

## State of the measurements

The closing corpus is committed and re-runnable. **39 convenes, 13 tickers × 3, 468 turns, all twelve
agents at exactly 39**, live against Alpha.

| Artefact | Path |
|---|---|
| Leg 5 corpus (turns) | `docs/forward_planning/CR143_agent_prompt_audit/corpus/llm_audit_2026-08-14-epoch.json` |
| Leg 5 corpus (runs) | `docs/forward_planning/CR143_agent_prompt_audit/corpus/room_runs_2026-08-14-epoch.json` |
| 08-13 baseline | same dir, `*_2026-08-13-epoch.json` |
| Sweep results | `docs/forward_planning/CR179_room_data_and_coherence_close/{leg5,baseline0813}_sweep.json` |
| Ticker list | `docs/forward_planning/CR035_room_benchmark/tickers_cr179_leg5.txt` |
| Corrected %-checker | `backend/scripts/cr179_leg5_pct_check.py` |
| Full findings | `docs/forward_planning/CR179_room_data_and_coherence_close/CR179_room_data_and_coherence_close.md` |

Results, baseline → Leg 5: **M1** 97.5 → 95.6% · **M2** +0.163 → +0.151 (role still beats ticker) ·
**M3 novel** 2.7 → 3.5% · **M6** 1.45 → 1.42 bits, 0 unanimous · **M7** 0.0 → 2.2% · **M8** 2.5 → 2.6% ·
**truncation** 1.2 → **0.2%** · **CR156 Tier B** 33% at filing → 2.6%.

**Both corpora are the same 13 tickers**, which is the only reason the comparison means anything
(DEF230 mix-shift). If you build a new epoch, hold the tickers constant or the numbers are not
comparable to any of the above.

**Acceptance 5 was overridden, on the record.** The plan pre-committed to *"if novel rises on a lane
this build widened, that lane is partially reverted."* Novel rose on seven lanes. Saiful's call
(2026-08-14) was **keep the lanes**, because M3 cannot tell a fabricated number from a computed one,
hand-reading showed the new novel numbers are correct derived scenarios, and the three lanes the plan
named as its own gates all *fell*. **The evidence for that call got weaker the same day** — the
supporting "the fabrication-sensitive metric is flat" became "3/40 vs 1–2/29, too few to call" after
the correction above. If a later epoch shows the derived-% class rising on those lanes, that is the
evidence the adjudication was wrong and the revert is back on the table.

---

## What is actually left

**Owed**

1. **Audit submission** — CR179 Legs 0–5 + DEF302, one submission (per-leg is no longer available
   retroactively). Hand the auditor the corpus, both sweeps, and the correction record. Ask them to
   challenge three things specifically: the acceptance-5 override, the corrected 3/40 vs 1–2/29 rates,
   and whether `primary_trend_line`'s new inverse removes the inversion or merely gives the model two
   numbers to confuse.
2. **Re-measure DEF302** — the fix is live on Alpha, so the corpus can now test it. **P2 applies: a
   rendering change is not a behaviour fix.** The claim currently supportable is "the ambiguity is
   gone from the input", not "the model stopped misattributing". ~50 min, same 13 tickers.
3. **`conservative_debator` `_AGENT_MAX_TOKENS`** — the single at-cap turn in 468 (headroom 1.00×,
   cap 800). One re-derivation owed; every other agent has 1.3–3.4×.

**Open, unexplained, not urgent**

4. **M7 0.0% → 2.2%** — one mismatched pair of 45, no hand-read behind it. The CR169 gate, and the only
   metric that moved the wrong way unexplained.
5. **M1 −1.9pt / M2 −0.012** — still 10.5× chance and role still beats ticker, but a wider shared sheet
   is the obvious candidate and it is the direction CR145 Tier C exists to defend.

**Saiful's call, carried from earlier**

6. **CR147 Tier C** — blocked on lxml.
7. **pytest-xdist** — assessed safe against `tests/conftest.py::_isolated_db` (per-test sqlite in
   `tmp_path`, ~20 singleton resets, mock providers pinned, no fixed ports). **Not installed** — new
   dependency, needs a decision.

---

## Rules that will bite you here

- **Registers are GENERATED.** Never hand-edit `docs/defect/def_list.md` or
  `docs/forward_planning/cr_list.md`. Write one row file (`_registry/DEF###.row.md`), run
  `python3 scripts/registers/gen_registers.py gen all`, commit row + table together. `python` is not on
  PATH; use `python3` or `backend/.venv/bin/python`.
- **Pathspec commits only** — `git commit -m "…" -- <your files>`. Never bare, never `-am`, never
  `git add -A`. The checkout is shared with ≥2 other lanes and their dirty state is routinely present.
- **Mac is a pure editor.** No backend, no DB, no Docker. Tests: `cd backend && .venv/bin/python -m
  pytest tests/unit/ -q` (~8–11 min, sqlite tempfile). Everything else goes to Alpha via
  `/promote-to-alpha`.
- **`/promote-to-alpha` rsyncs the whole tree**, so a promotion ships *everyone's* committed work, not
  just yours. That is how DEF302's fix reached Alpha on another lane's promotion. Check
  `git log --oneline -5` for an in-flight migration edit before promoting (DEF278).
- **DEF243's corollary** — do not edit a guard to accommodate a change. If one must move, keep its
  original reasoning verbatim and cite the evidence that moved it. `test_room_prompts.py:36` is a
  worked example from this session.
- **P2 / CR038** — prompt instructions are not controls. Agents ignore emphatic instructions ~70% of
  the time; DEF243 measured a rewording moving displacement 28.9% → 33.3%, i.e. nothing. If it must
  hold, make it structural.
- **The AI is named AMI** in anything a user reads. "LLM" is fine in code and internal docs.

---

## Verification quoted, not asserted

`4112 passed, 2 skipped, 13 warnings in 638.07s` — `.venv/bin/python -m pytest tests/unit/ -q`, exit 0,
2026-08-14, after the DEF302 fix. The pre-fix baseline on the same day was `4093 passed, 2 skipped`.

**What CR179 does NOT claim:** that the reasoning improved. M1/M2 measure distinguishability, M3
measures where numbers came from, M8 measures lane discipline. Twelve agents can be perfectly
distinguishable, perfectly grounded, perfectly laned — and all wrong.
