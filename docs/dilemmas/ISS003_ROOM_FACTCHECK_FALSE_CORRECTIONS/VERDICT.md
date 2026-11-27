# ISS003 — VERDICT

**Judged:** 2026-11-27 by the CR267 coordinator (track B), protocol step 6. All three folders read in full; the format-compliance measurement (`MEASUREMENTS/format_compliance_2026-11-26.md`) commissioned to test the one assumption two submissions rest on.
**Criterion (invite):** which design plausibly stops round 4 (the next unseen phrasing), and can a reviewer check that it does.
**Status:** recommendation. Saiful decides. Implementation is a new CR.

---

## 1. Ranking

**FABLE > LUNA > MAI_CODE2.**

1. **FABLE — winner.** The only submission that measured the problem, and the only design that removes the false correction without depending on the model writing a new format. Provenance by value: a desk figure that equals, at its own precision, any figure the desk was shown is a figure of record; the only user-visible sentence lists the desk's own figures and never states a sheet value.
2. **LUNA — runner-up.** Cite-by-ID claim ledger with typed sources. Weaker on evidence (no measurement, no prototype), but its revision found two real gaps in today's code (§4) that the winner must absorb.
3. **MAI_CODE2 — same family as LUNA, less complete.** Numeric atoms by ID, server renders every number. Strong guarantee on paper; the measurement in §3 shows the cost; its demo has a failing test.

All three agree on the part that matters most: **no user-visible sentence in AMI's voice says a desk's figure is wrong.** That is already true on Alpha (`ROOM_FACTCHECK_NOTES=log`, deploy #36) and stays true under every option.

---

## 2. What I verified (re-run, not trusted)

1. `FABLE/prototype/test_brief_cases.py`: **16 passed** (0.03 s), including the three `test_MISS_*` tests that pin what it does not catch (dropped sign, right number under the wrong label, an altered figure landing on another sheet figure).
2. `MAI_CODE2/test_provenance_demo.py`: **1 failed, 6 ran** — `test_round_three_values_can_be_published_from_each_source_class` expects "quoted single-name cap" and gets "single-name cap". A demo defect, not a design defect.
3. LUNA has no code to run.
4. LUNA's two code claims, checked in the source:
   1. under `ROOM_FACTCHECK_NOTES=log`, a Risk Officer `key_number` / `decisive_number` the check cannot corroborate is still treated as verified (`backend/app/services/risk_officer.py:395`, `:427`) — **true**;
   2. the `room_factcheck_finding` log carries `run_id` but no market or ticker (`numeric_quotation.py:1059`) — **true**.
5. Not re-run: FABLE's 369-Room replay (needs the Alpha export it kept out of the repo). Its numbers are consistent with what this session saw independently: the three ISS003 rounds and the bank measurement (CR287 phase 1), where FCF on bank sheets drove most of the noise.

---

## 3. The deciding measurement: can our models write cite-by-ID?

40 real desk turns (20 US, 20 Bursa), each model rewriting the turn as prose segments plus atom IDs; arm B with constrained decoding (digits forbidden in prose, atom IDs an enum). Full table in `MEASUREMENTS/format_compliance_2026-11-26.md`.

| Model | Valid after one repair (arm B) | Withheld | Median latency per call |
|---|---|---|---|
| Qwen (`qwen38-flash-next-abliterated-nvfp4`, Alpha's primary) | 95% | 5% | 16 s |
| Ling (`Ling-3.0-flash-Fin-fp4`, Alpha's backup) | 70% | 30% | 8 s |
| DeepSeek via CheapLLM (20 turns) | 95% | 5% | 133 s |

What decides it is not the validity rate:

1. **Only 62% of the numerals desks actually write equal any sheet figure** (US 55%, Bursa 69%). The rest are the desk's own arithmetic, mandate figures, levels and debate figures. Under cite-by-ID those either need a code-registered derived atom per formula — an open-ended registry, the same shape as the rule-list that failed three times — or they are dropped.
2. **Hand-read, 5–6 of 10 valid outputs per model attached an atom to the wrong thing or left it dangling.** Under cite-by-ID that error is rendered by AMI's own code as a labelled figure of record ("Cash flow remains TTM FCF: −RM15,433M." where the sentence was about something else). That is a new user-visible false statement in AMI's format, which is the exact harm ISS003 exists to remove.
3. The constraints leak: Ling wrote mathematical-bold digits past the digit pattern (4 Rooms); Qwen's atom enum was not enforced in 4 of 40.
4. Ling, the backup model, would withhold 30% of turns; a failover would blank a third of the Room.
5. Every repair adds a full model call (16–46 s on Qwen), and streaming waits for the whole turn.

So the strongest guarantee in the submissions costs, on the models we run, a large loss of what desks say plus a new class of AMI-rendered error. FABLE anticipated this and rejected cite-by-ID "for now, on the evidence"; the measurement supports that call.

---

## 4. What the runners-up contributed that the winner must absorb

1. **LUNA — the log-only Risk Officer gap.** Today a Risk Officer headline number passes as verified when the check cannot corroborate it. The implementation must route `key_number` / `decisive_number` through the provenance outcome: `record` → verified; `own` → not promoted to the headline, carries the provenance note. Close this first; it is a live gap.
2. **LUNA — "corroborates against any number in the corpus" is too weak** for the Risk Officer. FABLE's ledger has the same weakness by design (match by value). Accept it for prose, but for the Risk Officer headline require the match to come from the sheet or ladder block, not the debate.
3. **LUNA — telemetry.** Add market and ticker to the per-turn provenance event so US and Bursa gates can be measured separately without a join.
4. **LUNA — `hypothesis` as a source type.** Under FABLE this maps to desk-own figures in conditional sentences ("if FCF conversion recovers above 60%"). Keep FABLE's single note, but do not list figures inside an explicit conditional; FABLE's own sample shows thresholds and falsifiers are 11 of 120 listed figures.
5. **MAI_CODE2 — the final-serializer double scan.** Count numerals in the rendered string independently of the ledger and alert on a mismatch. Cheap and loud; use it as FABLE's per-turn breaker input.
6. **MAI_CODE2 / LUNA — the zero-correction invariant as a release check.** A test that fails the build if any code path can emit "the sheet's own figure is", or any "AMI checked … not X" string.

---

## 5. What was rejected, and what was right about it

1. **Cite-by-ID now (MAI_CODE2, LUNA).** Rejected on §3. Right about: the render boundary as the place a control lives, typed sources, and fail-loud behaviour. Revisit only if a later model writes the format with correct attachment in ≥ 9 of 10 hand-read turns and the derived-figure share is covered.
2. **A model as judge of each finding** (rejected by FABLE and LUNA independently). Agreed.
3. **More rules on today's matcher** (all three). Agreed; three rounds at ~0.5% precision (FABLE's replay).

---

## 6. FABLE's limits, accepted knowingly

1. **Dropped or flipped signs are not caught.** These were the only real misquotes in 369 Rooms (2, one 0388.KL turn). A "sign candidate" signal is logged, never shown, until it passes the same gate.
2. **About 21% of simulated alterations land on another sheet figure** (54% for whole-number percentages). Silent. FABLE's measurement says real alterations are rare; the nightly band (§7.4) watches the share of figures of record.
3. **Right number, wrong label** passes.
4. **Its own gate is not passed yet.** Its offline ledger lacked the mandate, feed and desk-specific blocks; built from the real prompt, the listed-figure rate must be re-measured before any market shows the note.

CR287 (deployed 2026-11-27) already removes the single largest source of today's false corrections: FCF on bank sheets.

---

## 7. Recommendation (for Saiful)

1. **Adopt FABLE's design** as a new CR, shadow-first: compute and log the provenance outcome per turn; show nothing until a market passes its gate.
2. **Gate per market** (FABLE §2.3): replay ≥ 300 Rooms, adjudicate 300 listed figures at random, pass on 0–1 false. US and Bursa separately. EN only; AR/MS need their own gate.
3. **First, in the same CR: close LUNA's Risk Officer gap** (§4.1) — the one live weakness of log-only mode.
4. **Production watch:** per-turn event with market and ticker; nightly replay with bands (share of figures of record, listed figures per Room, firing rate per Room); the per-turn breaker ("figure check unavailable for this turn") at more than 6 listed figures.
5. **Keep `ROOM_FACTCHECK_NOTES=log`** until the gate passes. Retire `annotate` mode and the field-spec matcher after a month of side-by-side logging.
6. **Adopt FABLE §9 as a house rule**, whatever is built: no sentence in AMI's voice that judges a desk's figure ships until it has been replayed over ≥ 300 stored Rooms per market and a sample of its firings adjudicated. Record it as a guard in `failure_patterns.md` (protocol step 8).
