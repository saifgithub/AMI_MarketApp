<!--
run_report.md — auditor run report, R68-BATCH8 round 1. Evidence behind the verdict in
orchestration/audit/cr/R68-BATCH8.auditor.md.
-->

# 2026-08-11 run-02 — R68-BATCH8 round 1 (DEF239 · CR156 B · DEF255 · CR156 D)

**SHA audited:** `e7efd472` (on `main`, on `origin/main`).
**Tree:** `git archive e7efd472 | tar -x` into a scratch dir — never the shared checkout (DEF159).
**Interpreter:** `/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python` (BINDINGS: absolute path, never bare `pytest`).
**Shared commit:** `e7efd472` also carries Batch 7. Only Batch 8's items audited here.

---

## 1. Tree provenance

```
$ git log --oneline -1 e7efd472
e7efd472 feat(room): the Room can see what the risk budget already spent, and the PM's verdict says what it means (AT:R68 CR153 CR154 CR155 CR156 DEF239 DEF255)
$ git branch -r --contains e7efd472
  origin/HEAD -> origin/main
  origin/main
```

16 files, 744 insertions. Batch 8's surface: `room_runner.py`, `room_prompts.py`,
`overlay_generator.py`, `content/agents/portfolio_manager.md`,
`docs/initial_specs/02_agents/safety_floor.md`, `test_cr156_def239_def255_pm_verdict.py`.

## 2. Independent suite

```
$ cd <scratch>/backend && "/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
2 failed, 3405 passed, 2 skipped, 13 warnings in 3379.39s (0:56:19)
```

Both failures are pre-existing load-induced timing flakes — §9.

Targeted, `-p no:randomly`:

```
$ pytest tests/unit/test_cr156_def239_def255_pm_verdict.py tests/unit/test_room_prompt_parity.py \
         tests/unit/test_p16_prose_pattern_corpus_parity.py tests/unit/test_def141_audit_pins_are_collected.py -q
30 passed in 29.16s
$ pytest tests/unit/test_cr156_def239_def255_pm_verdict.py --collect-only -q
20 tests collected in 0.62s
```

20 tests — matches the submission.

## 3. DEF239 — the allowlist, both directions

Own probe (`probe_batch8.py`, P1–P3), run against the extracted SHA.

**Scrape-bait — nine payloads, all correctly fall through to `_PM_NO_RATIONALE`:**

```
[OK] bare ticker only          {"action":"PASS","ticker":"AAPL"}                    -> NO_RATIONALE
[OK] non-prose strings         {"sector":"Technology","exchange":"NASDAQ"}          -> NO_RATIONALE
[OK] off-allowlist prose keys  {"note":"the debate was thin","summary":"no edge"}   -> NO_RATIONALE
[OK] empty narration           {"narration":""}                                     -> NO_RATIONALE
[OK] whitespace narration      {"narration":"   \n  "}                              -> NO_RATIONALE
[OK] null values               {"narration":null,"rationale":null}                  -> NO_RATIONALE
[OK] int narration             {"narration":42}                                     -> NO_RATIONALE
[OK] list narration            {"narration":["a","b"]}                              -> NO_RATIONALE
[OK] dict narration            {"narration":{"text":"nested"}}                      -> NO_RATIONALE
```

`{"ticker": "AAPL"}` is NOT rendered as a defence. DEF232's disclosure survives.

**Rescue direction — all six allowlisted keys surface prose:**

```
[OK] key=narration    -> 'Synthesis held; size cut to 1.5%.'
[OK] key=narrational  -> 'Synthesis held; size cut to 1.5%.'
[OK] key=rationale    -> 'Synthesis held; size cut to 1.5%.'
[OK] key=reasoning    -> 'Synthesis held; size cut to 1.5%.'
[OK] key=reason       -> 'Synthesis held; size cut to 1.5%.'
[OK] key=explanation  -> 'Synthesis held; size cut to 1.5%.'
```

Precedence: `_pm_narration({"reason":"B","narration":"A"}) == "A"`. Keys are
case-sensitive (`Narration` / `NARRATION` do not match) — correct, the key is
whatever the model emitted, and case-folding would widen the surface for no
evidenced gain. APPROVE path with prose under `rationale` returns
`action=APPROVE, reason="Bull case survives the bear rebuttal."`; APPROVE with no
prose at all still logs `room_pm_no_rationale` and carries the disclosure.

**CONFIRMED. Allowlist, not scrape. Both directions hold.**

## 4. CR156 B — every REJECT left in the assembled Room PM prompt

Reconstructed via `build_room_messages(agent_id=PORTFOLIO_MANAGER, …)`, 11,023 chars:

```
L   6: Approve, reject, or modify the proposed trade. …            (prose, profile role line)
L  31: Verdict:   APPROVE | REJECT | MODIFY-AND-APPROVE            (## Output format — covered by REPLACES)
L  49: … Like a veteran PM signing off on or rejecting trades.     (prose, Voice)
L  85: You are the gatekeeper. You approve or reject …             (prose, overlay)
L 123: YOU MUST REJECT any trade that:                             (SAFETY_FLOOR_BLOCK — NOT covered)
L 170: This output format and its two action values REPLACE **both** …
```

Both *decision sequences* are clean — `content/agents/portfolio_manager.md:27,32`
and `overlay_generator.py:523,527` now read PASS. `_normalize_pm_action("REJECT")`
still returns `"PASS"` defensively. The remaining imperative is
`backend/app/agents/safety_floor.py:129` — see MINOR 3.

**MODIFY canary — genuinely UNEDITED, diffed against the parent:**

```
$ git show --stat --format="" e7efd472 | grep -i parity
(no output — file not in the commit)
$ git diff e7efd472^ e7efd472 -- backend/tests/unit/test_room_prompt_parity.py
(empty)
```

`test_room_prompt_parity.py:68` (`assert any("MODIFY" in t for t in tokens)`) is
untouched and green. The CR105 Amendment-1 trap was avoided, not paid.

**`## Output format` block:**

```
'## Output format' in build_agent_prompt(PORTFOLIO_MANAGER, …)      : True
'There are exactly two action values' in that same prompt           : False   (_PM_VERDICT_FORMAT is Room-only)
'APPROVE | REJECT | MODIFY-AND-APPROVE' in that same prompt         : True
```

Kept, and it really is the 1-on-1 PM's only format instruction. Pinned by
`test_the_one_on_one_output_format_block_is_not_deleted`. **CONFIRMED.**

## 5. DEF255 — the rendered note, read as text

Verbatim at `horizon_days=1095, entry=100.0, stop=94.0`:

```
 (AMI: the stated horizon of 1095 days reaches beyond every input this decision had
 — 3 months of price history, TTM fundamentals and a 52-week range. Nothing on the
 fact sheet supports a thesis that long, and the 6.0%-below-entry stop is a
 weeks-to-months instrument — over that horizon ordinary volatility would take the
 position out long before the thesis could be judged.)
```

**Advice question — NOT a BLOCKER.** The sentence recommends nothing, sanctions
nothing, and states no rule about how long anyone should hold. It is scoped to the
evidence AMI itself supplied and critiques the internal coherence of the
simulator's own output. Cross-checked mechanically against the banned lists the
project already uses for this exact class (`test_def240_loud_concentration.py:57-64`):

```
DEF240 banned-word hits in the DEF255 note: NONE
```

`_MAX_EVIDENCED_HORIZON_DAYS = 365` is genuinely DERIVED, not chosen:
`technicals.py:42 _HISTORY_PERIOD = "3m"`, fundamentals are TTM, and the 52-week
range (`room_prompts.py:_week52_line`) is the widest window on the sheet. The
constant is never rendered as a holding rule. **CONFIRMED.**

**Boundary + degenerate inputs:**

```
365       -> ''            (inclusive, correct)
366       -> note fires
None / 0 / -5             -> ''    (no crash)
1_000_000_000             -> note fires, no overflow
horizon_days as "1095"    -> int()-coerced to 1095, note fires
horizon_days as 1095.7    -> 1095, note fires
stop ABOVE entry          -> stop clause correctly omitted
entry=None, stop=None     -> stop clause correctly omitted
```

**Flag, never veto:**

```
{"action":"APPROVE","size_pct":2.0,"entry":100.0,"stop":94.0,"target":113.0,
 "horizon_days":1095,"narration":"Long thesis."}
  -> action = VerdictAction.APPROVE      (APPROVE preserved)
  -> time_horizon_days = 1095            (not clamped, not rewritten)
  -> note present in verdict.reason      True
  -> note present in display/transcript  False
```

DEF059's sole-vetoer property is intact. **CONFIRMED.**

**Where it fails — see MAJOR 1 and MINORs 1–2.**

## 6. CR156 D — the composition claim, verified in code not prose

`agent_prompts.py:95` → `return append_safety_floor(composed, agent_id, mandate)`.
`room_prompts.py:577` → `base = build_agent_prompt(…)`; `room_prompts.py:741` →
`system_prompt = base + room_addition`.

Measured on the assembled PM Room prompt:

```
base ends with the floor terminator          : True
room prompt ends with the floor terminator   : False
floor starts at char 4979 / 11023            : 45% through the prompt
chars rendered AFTER the floor block         : 4647
text after the floor contains _PM_VERDICT_FORMAT : True
text after the floor contains the CONVENE block  : True
```

The doc's old claim was false on the Room surface. The correction is accurate.
**Documented-not-reordered is the right call** — reordering is a prompt-level
change to a mechanism CR038 measured at ~30%, and `enforce_safety_floor()` is the
actual control. Reordering would also put the JSON output contract ahead of the
transcript it must summarise. **CONFIRMED — but see MAJOR 2.**

## 7. Live measurement — reproduced on melehost, not read off the submission

```
$ ssh melehost "docker ps --filter name=ami_"
ami_api_alpha Up 24 minutes (healthy)   [started 2026-08-11T15:35:16Z]
$ docker exec ami_api_alpha grep -c "_MAX_EVIDENCED_HORIZON_DAYS" /app/app/services/room_runner.py  -> 2
$ docker exec ami_api_alpha grep -c "_PM_NARRATION_KEYS"          /app/app/services/room_runner.py  -> 2
```

The audited code IS deployed. Queried `room_runs` directly (read-only).

**CR156 B, "4 of 14 (28.6%)" on the 2026-08-11 post-promotion batch —
REPRODUCED, with one correction.** The 10:46–11:49 batch is exactly 14 verdicts.
`reason LIKE '%REJECT%'` (case-sensitive) hits 3: 11:02 NVDA, 11:10 AMZN,
11:23 WMT. The 4th is **11:27 SLB** — the DEF239 verdict itself, whose "REJECT:"
prose was suppressed into `_PM_NO_RATIONALE` and therefore *cannot* appear in the
stored column. The architect's cited timestamp (`2026-08-11 11:27:36Z`, SLB)
matches a real row exactly. 4/14 stands once that suppression is accounted for —
and the fact that the stored column can only show 3 is itself DEF239.

**DEF255, "4 of 13 approvals" at 1095 — PARTIALLY reproduced.** Four `1095` rows
exist across 08-09→08-11 approvals (1 on 08-10, 3 on 08-11). I could not
reconstruct the exact 13-approval denominator. Recorded, not scored.

**The note's real blast radius — my own measurement, not in the submission:**

```
approvals 2026-08-09 → 2026-08-11                    : 25
of those, time_horizon_days > 365                    :  7   (28%)
of those 25, level_provenance->>'stop' = 'ami_default': 0   (all 25 = 'pm')

ticker  horizon  entry    stop     stop distance
GIS       900    46.13    45.26     1.9%
MCHP     1095    62.66    61.00     2.6%
XPEV     1095    23.73    22.31     6.0%
STZ      1095   170.44   160.21     6.0%
NVDA     2520   223.96   200.00    10.7%
CRM      1095   265.18   227.35    14.3%
M         730    12.06    10.16    15.8%
```

**The DEF255 control has had ZERO live firings.** Only 7 runs since the 15:35Z
restart; the single APPROVE among them carries `horizon_days=180`. `0 of 149`
2026-08-11 verdicts contain "reaches beyond every input". Deployed, unexercised.

**One live `_PM_NO_RATIONALE` post-deploy** (STZ, 15:41:16Z log line
`room_pm_no_rationale action=PASS ticker=STZ`). The raw LLM object is not
persisted — only the display text is — so I could NOT verify whether an
off-allowlist key held prose in that verdict. Recorded as unverifiable.

## 8. Honest-omission check — are they omissions or quiet failures?

**`pm_verdict_corpus.txt` (811 rows) — honest omission, confirmed.** The fixture
is FROZEN (`test_p16_prose_pattern_corpus_parity.py:27-31`: "every real
`room_runs.verdict->>'reason'` string on Alpha (2026-08-08) that carries a `$`
figure"). Neither it nor `_DIRECTIONAL_CLAIM_RES` changed at `e7efd472`;
`_EXPECTED_EXTRACTIONS = 364` still passes. So no re-run is *forced*.

**DEF231's live rate genuinely does need re-measuring** — and the reasoning is
exactly right: verdicts whose prose used to store as `_PM_NO_RATIONALE` (no `$`,
so excluded by the fixture's own selection criterion) will now store real prose
carrying `$` levels. That IS an enlarged input population. Honest, and correct.

**The new note cannot contaminate that pipeline** (own check):

```
directional-pattern hits in the note (horizons 1095 / 2520 / 900) : []  []  []
note contains a "$" figure                                        : False
```

So the note neither adds corpus rows nor adds extractions. Clean.

## 9. Full independent suite result

```
2 failed, 3405 passed, 2 skipped, 13 warnings in 3379.39s (0:56:19)

FAILED tests/unit/test_def120_blocking_io_fix.py::test_marks_fetch_is_fast_warm_cache
FAILED tests/unit/test_def136_room_convene_does_not_block_loop.py::test_the_loop_never_stalls_while_the_builders_block
```

Both are wall-clock assertions, both pre-existing, both load-induced. A/B, five
runs of the two files at each commit, on a box carrying 19–25 concurrent `pytest`
processes from sibling audit sessions:

```
PARENT  4746e124 : 6 passed / 6 passed / 1 failed,5 passed / 6 passed / 6 passed
AUDITED e7efd472 : 6 passed / 6 passed / 6 passed / 6 passed / 1 failed,5 passed
```

Identical 1-in-5 rate either side. Both pass in isolation on re-run. Collection
total matches the submission: 3405+2+2 = 3409 vs 3408+1 = 3409.

An earlier full run at the same SHA was killed by the harness at 88% having
produced **zero** `F`/`E` markers — consistent with load-dependence, not a
regression.

## 9b. Mutation proof (auditor's own — the submission carries none)

Second `git archive e7efd472` copy, isolated from the suite tree.
Baseline: `20 passed in 31.65s`.

```
MUT-1  _PM_NARRATION_KEYS -> ("narration",)            6 failed, 14 passed   KILLED
MUT-2  free-text scrape fallback in _pm_narration      1 failed, 19 passed   KILLED
       (test_the_no_rationale_disclosure_still_fires_when_nothing_carries_prose)
MUT-3  _horizon_coherence_note turned into a veto      KILLED
       (test_an_incoherent_horizon_flags_but_never_vetoes)
MUT-4  _MAX_EVIDENCED_HORIZON_DAYS 365 -> 1000         KILLED
       (test_the_boundary_is_derived_from_the_widest_window_on_the_sheet)
MUT-5  stop_pct hardcoded to 6.0 (real stop ignored)   142 passed  SURVIVED
```

MUT-2 is the important kill — "allowlist, not scrape" is genuinely guarded, not
just asserted in a comment. MUT-5 is MAJOR 1's evidence.

## 10. Findings

| # | Severity | Where |
|---|---|---|
| 1 | **MAJOR** | `room_runner.py:1156-1162` — the stop clause's classification + predicted outcome are independent of the stop distance they name |
| 2 | **MAJOR** | `agent_prompts.py:77-78` — CR156 D's retracted ordering claim survives verbatim in the code, citing the doc that now contradicts it |
| 3 | MINOR | `room_runner.py:1150-1155` — "every input" / "Nothing on the fact sheet" enumerate three inputs while the sheet also carries forward P/E, analyst consensus target, next-earnings estimate |
| 4 | MINOR | `room_runner.py:1240-1250` — the note names an AMI-minted stop on the path where the PM stated none (zero live incidence) |
| 5 | MINOR | `safety_floor.py:129` — `SAFETY_FLOOR_BLOCK` still opens the violation clause "YOU MUST REJECT any trade that:"; CR156 B's sweep is not exhaustive |
| 6 | MINOR | 1-on-1 PM prompt still offers `APPROVE \| REJECT \| MODIFY-AND-APPROVE` with no reconciling sentence (out of CR156 B's scope; recorded) |

Detail and reproductions in `orchestration/audit/cr/R68-BATCH8.auditor.md`.
