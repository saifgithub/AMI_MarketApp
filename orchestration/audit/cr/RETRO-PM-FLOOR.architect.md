<!--
RETRO-PM-FLOOR.architect.md — audit lane. State derives from round numbers here vs
RETRO-PM-FLOOR.auditor.md. RETROACTIVE audit under programme CR231 / decision D-072: this work
was already built and promoted to Alpha (tag alpha-2026-09-24-1) WITHOUT the independent-audit
handshake — CR219 was accepted by a dispatcher, not the auditor. This submission is not a build;
it is the record the auditor needs to verify after the fact. GATE: independent.
-->

# RETRO-PM-FLOOR — audit lane (PM/safety-floor compliance perimeter, retroactive)

**SCOPE:** chunk — nine items (CR219, CR201, CR210, DEF384, DEF383, DEF352, DEF398, DEF230,
CR197, CR199) bundled as one lane because they all touch the PM verdict path that
`enforce_safety_floor` sits on, not because any one of them alone is Tier A.

**TIER: A.** Compliance-perimeter surface — this is exactly the "PM mandate enforcement is
uncoachable" floor CLAUDE.md names as behaviour-critical, plus "prompt instructions are not
controls" (CR038, ~70% ignored). Rounds uncapped until COMPLETE.

**SHA:** current `main` HEAD —

```
34941fa19cdc5bfa1a4739d5ad79386c75583232
```

(moved from `8c43c88e` while this lane file was being written — the one intervening commit,
`34941fa1`, is `docs(governance): CR231 stabilisation programme + DEF416-418 + D-072/D-073 +
back-filled review log`, the governance doc that authorizes this very retroactive audit. It does
not touch any file this lane discusses.)

This is a shared checkout, other lanes active concurrently — do not attribute commits below to
this lane that are not listed.

## Per-item commit list

**CR219** — `git log --format='%h %cs %s' --grep='CR219\b'` → **114 commits**, `839a12c2` (2026-09-02)
through `a61df393` (2026-09-17). Summarised by area rather than listed individually:

- **Fact-sheet/persona contradiction sweep** (the CR's own premise — 15 findings in 5 classes:
  personas denying LIVE fields, instruction-vs-instruction collisions, horizon-dependent demands
  for data no tool supplies, stale defaults, a fourth citation site) — `839a12c2`, `c9ab1078`,
  `46b2f745`, `3420fe74`, `3ae20272`, `41a18e4a`, `e394b1d3`, `955349bc`, `ecb8f199`, and the
  dispatcher-acceptance docs commits that flip individual R-numbered findings from proposed to
  built (`ec226c68`, `1f8f417a`, `bbc927bd`, `39ae7757`, `c1190f75`, `a278b344`, `699a8f7c`,
  `fba99bb9`, `f505c129`, `f519bf5b`, `c8ebfa67`).
- **New data/derivation work unblocking specific findings** — earnings revisions (`ecb8f199`),
  interest coverage (`ab9decb2`), explicit capex line (`a841ac13`), buyback pacing (`c7c40213`),
  ATR(14) (`a4459b01`), own-history median multiples (`d3943aa5`), debt-split design note
  (`ecbbd4b7`, design only — R38 not built in this window per the CR219 row's own accounting).
- **PM-verdict-adjacent findings — the ones this lane cares about most directly:**
  - `2fd4d688` (R51) — count/disclose/cap scripted-fallback turns, "DEF059's rule extended from
    'no AMI' to 'not enough AMI'".
  - `e9733883` (R50) — code-generated Room scoreboard in the CIO's context, "a missing envelope
    renders unparsed, never dropped".
  - `b1ea0901` (R49) — floor-state preview in the CIO's VERDICT context, explicitly "the floor's
    own helpers, never a second implementation" — i.e. this reads floor state, it does not
    reimplement or bypass it.
  - `683b5346` + `94672fe8` (R52) — kill-criterion field on the CIO verdict, schema+ask+tests in
    one commit.
  - `886355e4` (DEF398, filed and fixed inside the CR219 window — see below).
  - `0f9cc06d` — key_number/decisive_number checked against sheet+ladder before rendering (a
    content-accuracy guard, not a floor-bypass surface, but touches what the PM's rendered verdict
    is allowed to assert).
  - `14221679` (R53+R57) — permanent turn telemetry, GAPS tail + envelope emission.
  - `f16507da`/`e0c15b12`/`72da5c08`/`2884da95` — CR210 cross-references and aggregate_arms fixes
    (harness-side, not the live PM path).
- **Governance/process** — reviewer packages (GLM/QWEN/fable, `18e50562`/`3f19dfe8`/`0379b5f9`/
  `90ff31b4`), the "build-all" ruling (`234d5dde`), the checkpoint memo commit (`abb5f242`, docs
  only), the P33 one-writer-rule note (`57838b8e`).

Full range for independent review: `git log --oneline 839a12c2^..a61df393 --grep='CR219\b'` (or
`git log --format='%h %cs %s' --grep='CR219\b'` for the flat list this section summarises).

**CR201** — `git log --format='%h %cs %s' --grep='CR201\b'` → **23 commits** (`989f4c6d`
2026-08-20 through `7209e78b` 2026-08-21, plus one CR219-window touch `0f9cc06d`/`14221679`
tagged jointly — those two are counted under CR219 above, not double-counted here). Core: file
the structured Risk Officer (`989f4c6d`), delivery sweep + content/marketing amendments
(`53a3e370`, `c6113177`, `2167dd06`, `1c82d142`, `d5025524`, `3ce57cbd`), backend build
(`61c79b7f`), the DEF352 discovery-and-fix inside CR201's own re-measurement discipline
(`0cf99b69`, `793872fc`, `d03fe2bc`), enable-on-Alpha (`4daf404e`, `a827127a`, `7209e78b`).

**CR210** — `git log --format='%h %cs %s' --grep='CR210\b'` → **19 commits** (`92954347`
2026-08-25 through `fdf5f144` 2026-09-21). File (`92954347`, `3885a9f0`), build behind two flags
(`9b6e758d`), acceptance-2 (`21bbdb2a`, `010cc3c1`), the fix that banked the acceptance-2 arms
(`49380813`), DEF398 leg-2's dependency on CR210's grammar being the structural close
(cross-referenced, not this CR's own commit), and the still-open Acceptance-4 gap (DEF412,
`3785cbbc`, `fdf5f144` — **stays open**, see Attack surface).

**DEF384** — `a632476d` (2026-08-31) — **1 commit**, filed and fixed together (interleaved with
DEF383 and CR214 in the same commit — see below).

**DEF383** — `a632476d` (2026-08-31) — same commit as DEF384. Both defects were found and fixed
in one commit because they share a root cause (a defaulted-off branch, `pm_self_consistency_samples
> 1`, that CR214's own default-raise was the first thing to ever execute) and CR214 is what
surfaced both. `git show --stat a632476d`:

```
backend/app/agents/safety_floor.py                 |   8 +
backend/app/core/config.py                         |   7 +-
backend/app/schemas/room.py                         |  20 ++
backend/app/services/room_runner.py                 |  50 ++++-
backend/scripts/backtest_report.py                  | 208 ++++++++++++++++++++-
backend/tests/unit/test_cr077_phase_parallelism.py  |  29 ++-
```

**DEF352** — `git log --format='%h %cs %s' --grep='DEF352\b'` → **3 commits**: `0cf99b69`
(2026-08-21, the fix itself), `d03fe2bc` (the CR201 re-measurement that used it), `886355e4`
(2026-09-03, DEF398's fix references DEF352's recovery mechanism as the thing its own quoted-brace
case defeats).

**DEF398** — `git log --format='%h %cs %s' --grep='DEF398\b'` → **6 commits**: `886355e4`
(2026-09-03, leg 1 — `raw_decode()` before the `rfind` trim), `f6b14064` (reopen — leg 2 unblocked
not deployed), `b19052e9` (leg 2 marked closed prematurely — see below), `6394a3dc` (path-derivation
fix for the corpus-replay test blocking promotion), `9fc33bfd` (leg 2 actually deployed,
`alpha-2026-09-03-3`, verified via `printenv` inside the running container), `4697094a` (CR219
R30/R38/R43 ruling that references DEF398's R43 origin).

**DEF230** — `git log --format='%h %cs %s' --grep='DEF230\b'` → **12 commits** (`76cd7cdc`
2026-08-07 through `f4546137` 2026-08-18). Statistical-investigation defect, not a code fix — see
Attack surface for why it belongs in this lane anyway.

**CR197** — `git log --format='%h %cs %s' --grep='CR197\b'` returns 25 hits but several are
*cross-references from other CRs' commits* (CR228, CR172, CR201, CR164 mentioning CR197 in their
own subject/body), not CR197's own commits. CR197's own work: `bb62b77d` (file), `cc33e3e5`,
`64915d97`, `69497a7e`, `feafbad5`, `78a7a35a`, `ad1d5553`, `3db38db9`, `2f301759`(cross-ref,
excluded), `175dbeb1`, `b386f3b3`, `e2e2ff9d`, `f1ec9717` (restore after CR160 swept its
uncommitted lines — see DEF159-class incident noted in the row), `b2a8f263`, `be6a1bfc` — **15
commits** are CR197's own; `793872fc`, `a632476d`, `0f9cc06d`, `466c7500`, `56428880`, `32fed4fe`,
`6cb2edcf`, `c8543a12`, `da88ddb6`, `0d0f934d` are other CRs' commits that reference CR197 in
prose and are excluded from this count. Full command for independent recount:
`git log --format='%h %cs %s' --grep='CR197\b'` (25 raw hits — auditor should re-derive the
15/10 split rather than trust this line).

**CR199** — `0d39b918` (2026-08-20) — **1 commit**. Stage-ablation measurement CR, 952 live
calls, no production code path changed (Bull/Bear stay in the Room; the CR's own finding is "keep
the phase", not a code change).

**depends-on:** none between these nine at the lane level, but **DEF383 and DEF384 are the same
commit** and **CR201/CR210/DEF398/DEF352 form a real dependency chain in time** (CR201 shipped →
DEF352 found in CR201's own re-measurement → DEF398 found the same discard class again on CIO
verdicts inside CR219 → DEF398 leg 2's structural close is CR210's grammar). The auditor should
read them in that order, not independently.

**Promoted:** yes — **alpha-2026-09-24-1**. This is the entire reason for the retroactive lane:
none of these nine items passed through this audit handshake before shipping. CR219 was accepted
by a dispatcher (per this task's own framing); CR201/CR210/DEF352/DEF398/DEF384/DEF383 show no
`*.auditor.md` lane file anywhere in `orchestration/audit/cr/` for any of these IDs (checked:
`ls orchestration/audit/cr/ | grep -iE 'CR219|CR201|CR210|DEF384|DEF383|DEF352|DEF398|DEF230|CR197|CR199'`
returns nothing before this file).

## The central question this lane exists to answer

Per CLAUDE.md: *"PM mandate enforcement is uncoachable. Hard floor in PM prompt + deterministic
compliance check"* and *"Prompt instructions are not controls."* After CR219/CR201/CR210/
DEF384/DEF383/DEF352/DEF398/DEF230/CR197/CR199, **does every Room verdict that reaches a user
still pass through `enforce_safety_floor` (`backend/app/agents/safety_floor.py:913`), and can any
LLM output path — vote, repaired verdict, grammar fallback, Risk Officer — bypass or soften it?**

## What the source shows, read at the current SHA

`backend/app/services/room_runner.py`, the PM verdict block (function body spans roughly
lines 5495–5724 of the live-PM `elif live:` branch):

- **Three ways `parsed: Verdict | None` gets set** — the self-consistency vote (`_voted`, when
  `pm_self_consistency_samples > 1`), the LLM-outage path (`raw_text` empty → `_pm_outage = True`,
  never assigns `parsed`), and the single-draw path (`_parse_pm_verdict`, with one reformat retry
  restricted to recovering an APPROVE only — DEF067's rule, comment at line ~5634).
- **One shared decision tail** (comment block at line 5655, "DEF384 — ONE decision tail for every
  branch above… Do not re-inline this per branch"): `if not _pm_outage:` then either (a)
  `parsed is None` → hardcoded PASS with `overridden_from_llm=True` (fail-safe, DEF059's rule),
  (b) `parsed.action == APPROVE` → builds a `ProposedTrade` and calls `enforce_safety_floor(...)`
  at **line 5696, the only call site in this function** — this is exactly what DEF384's own guard
  test (`test_there_is_exactly_one_enforce_safety_floor_call_in_the_verdict_block`) pins by AST
  walk, or (c) any other action → `verdict = parsed` directly, commented "PASS — nothing to check
  compliance on" (a non-APPROVE verdict has nothing for the floor to veto; this is the documented,
  narrow carve-out, not a second path to an unchecked APPROVE).
- **The vote branch does not assign `verdict` directly anywhere** — confirmed by reading the block:
  `_voted` only ever populates `parsed` (line 5552) and appends telemetry (`approve_votes`,
  split-team disclosure, DEF397's short-vote disclosure), never touches the `verdict` name until
  the shared tail. This is the exact shape DEF384's guard
  (`test_the_vote_branch_does_not_assign_the_final_verdict`) exists to keep pinned.
- **`_pm_outage` short-circuits the tail entirely** and assigns `verdict` directly at line 5614 —
  the one place in the function `verdict` is set before the shared tail — but that assignment is
  a hardcoded `PASS` (`PM_LLM_UNAVAILABLE_REASON`, `overridden_from_llm=True`), never an APPROVE,
  so there is no path from "LLM unreachable" to an unchecked buy.

This matches DEF384's own row-file claim exactly — read independently here, not taken on the
row's word.

## Per-item claims vs. what I verified

| Item | Claim | Verified how |
|---|---|---|
| DEF384 | Vote branch used to bypass the floor; fixed with one shared decision tail | Read `room_runner.py:5495-5724` at current HEAD; confirmed single `enforce_safety_floor` call site, vote branch binds `parsed` not `verdict`. Ran `test_def384_vote_reaches_safety_floor.py` (4 tests) — see below |
| DEF383 | Vote branch crashed on `.action.value` (str after `use_enum_values=True`); fixed to `str(verdict.action)` | Read `room_runner.py:5582` — `action=str(parsed.action)`. `Verdict.model_config` at `backend/app/schemas/room.py` — did not independently re-grep `use_enum_values=True` this round; row file's reproduction (`_vote_pm_samples(...)` returns plain str) is specific enough to trust structurally, flagged for auditor's own re-check |
| DEF352 | Trailing prose after a complete `{...}` object was discarded wholesale; fixed with an `rfind('}')`-bounded retry | Ran `test_def352_trailing_prose_after_json.py` — passed (bundled in full-suite run, see below) |
| DEF398 | `rfind`-based recovery (DEF352's fix) itself defeated by a stray brace inside quoted prose; leg 1 = `raw_decode()`-first fix; leg 2 = CR210's grammar makes the whole class unrepresentable, deployed `alpha-2026-09-03-3` | Ran `test_def398_pm_json_contract_break.py` — passed. Leg 2's live-deploy claim (`printenv` inside `ami_api_alpha`) is **not independently re-verified this round** — no melehost check run; flagged in Attack surface |
| CR201 | Single Risk Officer call replaces 3-way debate, measured equivalent (net 0, p=1.0) after DEF352 fix; enabled on Alpha | Ran `test_cr201_risk_officer_room.py` — passed. Did not re-run the live statistical measurement (retroactive — no live corpus access this round) |
| CR210 | Grammar-constrained output on PM verdict / Risk Officer / Trader block, behind two flags, both **live on Alpha since `alpha-2026-09-03-3`** per DEF398's own row | Ran `test_cr210_constraint_plumbing.py`, `test_cr210_outcome_taxonomy.py`, `test_cr210_room_wiring.py`, `test_cr210_schemas.py` — all passed. **CR210's own row is still `in_progress`** — Acceptance 4 unsatisfiable from banked arms (DEF412, model-swap confound), flagged below |
| CR197 | Single structured Risk Officer proposal + CIO self-consistency + option ladder; explicitly "safety floor: unchanged" in its own scope | Ran `test_cr197_pm_self_consistency.py`, `test_cr197_risk_officer.py`, `test_cr197_size_envelope.py`, `test_cr197_option_ladder.py` — all passed |
| CR199 | Bull/Bear ablation — measurement only, no path change | Row states no production code changed; nothing to test against the floor |
| DEF230 | "Zero APPROVE since 07-30" investigated and closed as NOT a floor-firing issue (`violations: []`, `overridden_from_llm: false` on every recent run) — a prompt/tier/mandate-version confound, not a bypass | No code guard exists (row is a measurement writeup, closed by re-accrued traffic + a controlled n=40 replay, not a fix) — this is **expected**, not a gap, and is why it is `Recorded, not scored` for test-command purposes below |

## Tests, commands and observed output

**Targeted (safety-floor + all nine items' own test files), run bare, current working tree
(shared checkout — not a scratch worktree; see caveat below):**

```
cd backend
.venv/bin/python -m pytest tests/unit/test_safety_floor.py tests/unit/test_room_runner.py \
  tests/unit/test_def384_vote_reaches_safety_floor.py tests/unit/test_def398_pm_json_contract_break.py \
  tests/unit/test_def352_trailing_prose_after_json.py tests/unit/test_cr197_pm_self_consistency.py \
  tests/unit/test_cr197_risk_officer.py tests/unit/test_cr197_size_envelope.py \
  tests/unit/test_cr197_option_ladder.py tests/unit/test_cr201_risk_officer_room.py \
  tests/unit/test_cr210_constraint_plumbing.py tests/unit/test_cr210_outcome_taxonomy.py \
  tests/unit/test_cr210_room_wiring.py tests/unit/test_cr210_schemas.py -q
```

```
333 passed in 130.88s (0:02:10)
```
Exit code 0.

**Full backend unit suite:**

```
cd backend
.venv/bin/python -m pytest tests/unit/ -q -p no:cacheprovider
```

Full unit suite: not cited this round — 5 concurrent full-suite runs on the shared Mac checkout
(Architect's dispatch error); per-lane test results above are the builder evidence. Auditor
re-runs the independent suite on melehost per BINDINGS.

**Caveat on both runs (DEF159's own rule, stated rather than silently skipped):** both were run
in the shared working tree at `/Volumes/Extreme Pro/AMI_MarketApp/backend`, not a scratch worktree
pinned to the SHA above. This is a **retroactive record-review lane**, not a build submission —
there is no new source to measure at a specific commit; the point of these runs is "does the
current committed state of the safety-floor path still pass", and the working tree's
`git status --short` was checked clean of relevant changes before each run (no uncommitted diff
under `backend/app/agents/safety_floor.py`, `backend/app/services/room_runner.py`,
`backend/app/schemas/room.py`, or any of the nine items' own test files). The auditor should still
re-run in its own worktree per binding, since a shared checkout can have another lane's
in-flight edit land between my run and the auditor's.

## Measurement

**None run by builder — retroactive.** Every statistical claim in the per-item table above (CR201's
net-0 p=1.0, CR210's acceptance figures, CR197's ablation numbers, CR199's 952-call ablation,
DEF230's n=40 replay) was measured by the original build lane against live Alpha/vLLM traffic at
build time, not reproduced by me this round — I have no live Room-convene access in this session
and this is explicitly a record-and-code-review pass, not a re-run of the original experiments.
**Auditor to probe live Room verdicts on Alpha** (`alpha-2026-09-24-1`) directly: a mandate with a
post-loss cooldown or open-risk breach, run with `pm_self_consistency_samples` at both 1 and >1,
confirming the floor vetoes an LLM APPROVE identically at both settings — this is the one claim in
this lane a live probe can falsify that a code read cannot.

## Attack surface

**Deterministic-path bypass when a PM vote is present (DEF384).** The historical bug, fixed —
confirmed by source read above and by the AST guard (`test_there_is_exactly_one_enforce_safety_floor_call_in_the_verdict_block`)
passing. Residual risk: the guard pins *count* (exactly one call site), not *reachability* — it
would not catch a new branch added *before* the shared tail that assigns `verdict` directly and
`continue`s/`return`s past it. I did not find such a branch reading the current function, but the
guard's own blind spot is worth the auditor's own read, not just trusting the count.

**Repaired/clipped verdicts (DEF352, DEF398).** Both are pre-floor text-extraction fixes — they
change whether `parsed` gets populated at all, not what happens to `parsed` once it's an APPROVE.
Neither fix touches the shared decision tail or the `enforce_safety_floor` call. The class both
defects come from (DEF058→DEF067→DEF352→DEF398, four occurrences on the same failure shape per
DEF398's own row) is explicitly named as recurring — DEF398's row states the *third* occurrence of
this exact class triggered CR185's "third time ⇒ Dilemma" rule was considered and the structural
fix (CR210's grammar) was chosen instead of a fifth point-patch. Worth the auditor's judgment: is
CR210's grammar actually closing the class, or is it another point-fix that happens to be bigger?
CR210's own row says Acceptance 4 (the before/after that would answer "does the grammar change
model behavior, not just structure") is **unsatisfiable from the banked arms** (DEF412 — a model
swap confounds the only available before/after) and the row is still `in_progress`. That is a real
gap: the structural claim ("this class becomes unrepresentable") rests on the grammar being
correctly scoped, and CR210's row itself documents `regex_S5`'s first draft would have
manufactured a DEF288-class defect (a false "no R:R stated" claim) had it shipped as first written.
The corrected version shipped; the point stands that grammar constraints are not automatically
safe merely for being structural — they must be checked against the same DEF040/DEF288-class
false-claim failure modes as prose.

**Grammar-unsupported fallback.** CR210's row states the tolerant (DEF352/DEF398-hardened) parser
remains the fallback for any provider that cannot enforce a schema, and `llm_audit.constraint_status`
records five states including `unsupported` distinct from `NULL`. I did not independently verify
this enum or its distinctness this round — read from the row only, not from `llm_audit`'s schema
or a live query. Flagged as unverified rather than silently assumed.

**Risk Officer output reaching a verdict without the floor.** CR201's row states explicitly
"safety floor: unchanged (sole vetoer, DEF059)" and the Risk Officer's output feeds sizing/prose
on an *already-decided* verdict, not the APPROVE/PASS decision itself — the floor sits on the PM's
verdict, and the Risk Officer never returns a `Verdict`. Confirmed structurally: `AgentId.RISK_OFFICER`
sits outside `TWELVE_AGENT_IDS` per the row, and `_run_risk_officer()` is a rendering call, not a
verdict-producing one. I did not read `risk_officer.py` line-by-line this round to confirm it has
no code path that could construct or short-circuit into a `Verdict` object — flagged for the
auditor, since "the row says it doesn't" is the row's word, not an independent read.

**Feature flags that switch paths.** Three flags now gate PM-adjacent behavior:
`ROOM_RISK_OFFICER_ENABLED` (CR201, on since 2026-08-21), `ROOM_JSON_CONSTRAINTS_ENABLED` +
`ROOM_TRADER_REGEX_ENABLED` (CR210, on since `alpha-2026-09-03-3` per DEF398's row, env-only —
code defaults stay `false`), `pm_self_consistency_samples` (CR197/CR214, default 1, raised in
production per DEF384's own row — "Saiful chose 'production too' for CR214"). None of these are
documented in this lane as forwarded through `docker-compose.yml`'s `api-alpha` block for
CR040/DEF038/DEF063 compose-parity — I did not check `test_config_compose_parity.py` against
these three specific keys this round. That is a real gap in this submission: CLAUDE.md's own
degrade-loudly rule names exactly this failure mode (a config-gated feature dark for months), and
I have not confirmed these three keys are forwarded. Flagged, not verified.

**Fail-open behaviour when the LLM is down (DEF059 class).** Read directly in the source above:
the `_pm_outage` path hardcodes PASS with `overridden_from_llm=True`, never an APPROVE — this is
the DEF059 rule ("LLM down → confident fake APPROVE is the thing that must never happen") holding
at the one place in this function it could fail. No dedicated `test_def059_*` file exists;
coverage is distributed across many other test files that assert PASS-on-outage as a shared
invariant (`test_def256_json_control_chars.py`, `test_def258_pm_verdict_truncation.py`,
`test_def232_pm_empty_rationale.py`, and others — grep for `PM_LLM_UNAVAILABLE_REASON` across
`backend/tests/unit/` returns 10+ files). I did not enumerate and re-run all of them individually
beyond what the full suite run below covers.

**DEF230 — not a code bypass, but the compliance-perimeter question it raises is unresolved by
code.** DEF230 investigated a 100%-PASS drought and concluded the floor was *not* firing
(`violations: []` on every run) — the PM itself was choosing PASS, driven by a thickened
prompt-constraint set (CR101-BE2's mandate fields) with no bullish technical counter-signal
available. That is the opposite direction of risk from everything else in this lane (over-blocking,
not under-blocking), but it is the same underlying fact worth restating: **the floor's correctness
was never in question in DEF230** — what was in question, and left only partially answered (row
says "the mid tier is still underpowered... a monitoring question, not a defect"), is whether the
*prompt* surrounding the floor produces a Room that is unusable in the other direction. Out of
scope for "can the floor be bypassed", in scope for "is the compliance perimeter, taken as a whole,
behaving as intended" — flagged for the auditor's judgment on whether that reading question
belongs in this lane or a separate one.

## Governance

No new register items minted by this submission — all nine items are pre-existing, already
`done`/`fixed`/`closed`/`in_progress` in their registers (CR210 alone is `in_progress`, per its
own DEF412 gap, not because of anything found in this audit pass). This lane file does not change
any row's status; that is the auditor's and/or Saiful's call once the verdict lands.

## Known limits, stated rather than left to be found

- **No scratch-worktree measurement** (see caveat above) — a retroactive record-review choice,
  not an oversight; flagged for the auditor's own independent worktree run per binding.
- **No live melehost/Alpha probe run by builder** — the "measurement" section names exactly what
  the auditor should run that I could not.
- **DEF383's `use_enum_values=True` claim** not independently re-confirmed in `schemas/room.py`
  this round (see per-item table).
- **`risk_officer.py` not read line-by-line** for a hidden verdict-construction path (see Attack
  surface).
- **Compose-parity for the three PM-path flags not checked** (see Attack surface) — this is the
  gap I would most want the auditor to chase first, since CLAUDE.md names it as the single most
  repeated failure class (DEF038, DEF063) and I have not ruled it out here.
- **CR219's 114-commit range is summarized by area, not individually attributed to safety-floor
  relevance** — the per-item table above lists the ones I judged most floor-adjacent; the full
  range command is given for the auditor to re-derive independently rather than trust my triage.

SUBMITTED: round 1

## Round 2

**Branch:** `worktree-agent-a94c7459e971e99bf` (isolated worktree off `main`). **Commit:**
`692f9324801816e69230d86570c56977568d0f1b` — `merge-base` against `main` is `68f9c7d0`
(current `main` HEAD at task start), so this is one commit clean on top, nothing else in flight.
`diff --stat main...HEAD`:

```
backend/app/services/llm_json.py                   |  39 ++
backend/app/services/room_runner.py                | 143 ++++++-
backend/tests/unit/test_def398_pm_json_contract_break.py |  27 +-
backend/tests/unit/test_retro_pm_floor_round2.py    | 461 +++++++++++++++++++++
4 files changed, 657 insertions(+), 13 deletions(-)
```

New test file: `backend/tests/unit/test_retro_pm_floor_round2.py` (6 tests, one per
MAJOR/MINOR reproduction except MAJOR-2 which gets a functional test plus a unit-level pin
on `_build_room_sector_context` itself). Each was written from the auditor's own probe shape,
confirmed red on pre-fix code, then green after the fix — shown below per finding, plus a
separate revert-fix/red/restore mutation pass on the shipped fix itself (not the same thing:
the first proves the test reproduces the bug, the second proves the fix is what makes it pass).

### MAJOR-1 — respawn judged the floor against a fabricated $100k/0%-drawdown portfolio

**Fix:** `backend/app/services/room_runner.py:4532-4606` (`_respawn_run_from_row`). Before
constructing the event queue or spawning `_pump`, resolve the user's REAL portfolio snapshot
the same way `api/room.py` does (`sim.valuation_snapshot`, off-loop via `asyncio.to_thread`) and
pass both values into the eventual `self.run(...)` call (`:4613-4619`, `portfolio_value=`,
`current_drawdown_pct=` added to the call). If the snapshot read raises, the function logs
`room_startup_retry_snapshot_failed` at ERROR, marks the row `status="failed"` with a disclosed
`error_message`, and returns — no `self.run()` call happens at all, so there is no path from
"snapshot unreadable" to any verdict, fabricated-input or otherwise.

**Tests:**
`backend/tests/unit/test_retro_pm_floor_round2.py::test_respawn_reads_the_real_portfolio_not_the_run_defaults`
(control: `api`-shaped call with a real 50%-drawn-down user REJECTs on the drawdown cap; respawn
path, driven end-to-end through `_respawn_run_from_row` + `subscribe`, must land the same REJECT)
and `::test_respawn_fails_loudly_when_the_real_snapshot_cannot_be_read` (forces
`sim.valuation_snapshot` to raise; asserts `status="failed"`, no APPROVE, and a non-empty
`error_message`).

```
cd backend && .venv/bin/python -m pytest tests/unit/test_retro_pm_floor_round2.py::test_respawn_reads_the_real_portfolio_not_the_run_defaults tests/unit/test_retro_pm_floor_round2.py::test_respawn_fails_loudly_when_the_real_snapshot_cannot_be_read -q -p no:cacheprovider
2 passed in 5.25s        EXIT=0
```

**Confirmed red pre-fix:** run against the code before the fix (`self.run()` called with neither
kwarg) — `test_respawn_reads_the_real_portfolio_not_the_run_defaults` failed with the respawned
run landing `APPROVE` (fabricated $100k/0%-drawdown book) where the control REJECTed on the
user's real 62%(-equivalent) drawdown; `test_respawn_fails_loudly_...` failed with
`status='completed'`, a full `APPROVE` verdict — the exact "silent fallback to a fabricated
default" MAJOR-1 names, since pre-fix code never even calls `valuation_snapshot` and so never
notices the injected failure.

**Mutation (reverted after):** dropped `portfolio_value=`/`current_drawdown_pct=` back off the
`self.run(...)` call inside `_pump` (the exact pre-fix call shape) —
`test_respawn_reads_the_real_portfolio_not_the_run_defaults` → **1 failed** (respawn APPROVEd
against the fabricated $100k/0%). Restored; file diff clean (`git diff --stat` shows no
`MUTATION-TEST` markers remaining anywhere).

### MAJOR-2 — a sector-context failure silently switched off the max-open-positions cap

**Fix:** `backend/app/services/room_runner.py:1787-1841` (`_build_room_sector_context`). Split
the single try/except into two: the first reads holdings alone (`sim.ensure_portfolio` +
`list(portfolio.holdings)`) and returns `None` (not `[]`) for holdings on failure — the floor's
own "not supplied, block loudly" sentinel per `check_mandate_compliance`'s documented contract.
The second wraps only the sector-specific work (`current_marks`, `default_sector_map`,
`allocate_by_sector`) and on failure returns the **already-read** `holdings` unchanged, with
`sector_map=None`/`weights={}` — a resolver failure now costs the sector cap only, never the
position-count cap. `user_id is None` (the pre-existing "caller never asked" case) also now
returns `None` for holdings rather than `[]`, matching `_build_room_risk_limit_context`'s sibling
sentinel convention. `_RoomContext.sector_holdings` retyped `list | None`; the one direct
iteration consumer (`_build_room_option_candidates`'s `shares_held` sum, `:5372-5378`) guarded
with `ctx.sector_holdings or ()` — a cosmetic option-sizing input, never the compliance check, so
degrading to "no held shares" on `None` is the safe direction.

**Tests:**
`::test_sector_context_failure_still_blocks_the_max_open_positions_cap` (control: healthy sector
resolver, 2 real holdings via `SimHoldingRow`, `max_open_positions=2`, PM APPROVEs a 3rd ticker →
REJECT; failure path: `default_sector_map` forced to raise → must still REJECT, not APPROVE) and
`::test_sector_context_builder_reports_holdings_as_none_on_failure` (unit-level pin: a holdings
-read failure — `ensure_portfolio` itself raising — must return `None`, never `[]`).

```
cd backend && .venv/bin/python -m pytest tests/unit/test_retro_pm_floor_round2.py -k sector -q -p no:cacheprovider
2 passed in ~4s        EXIT=0
```

**Confirmed red pre-fix:** the failure-path run landed `APPROVE viol=[]` against the exact
control shape that REJECTs at `viol=['opening MSFT would exceed the max open positions cap
(2) — 2 already held']` — matching the auditor's own probe verbatim. The unit-level pin failed
with `assert [] is None`.

**Mutation (reverted after), two of them since the fix has two failure branches:**
1. Reverted the holdings-read branch's `return None, {}, None, {}` back to `return [], {}, None,
   {}` → `test_sector_context_builder_reports_holdings_as_none_on_failure` **1 failed**
   (`assert [] is None`).
2. Reverted the sector-only branch's `return holdings, {}, None, {}` back to `return [], {}, None,
   {}` (the ORIGINAL bug shape: a sector-resolver failure discarding already-read holdings) →
   `test_sector_context_failure_still_blocks_the_max_open_positions_cap` **1 failed** (`APPROVE`
   where control `REJECT`ed).

Both restored; `git diff --stat` clean of markers.

### MINOR-1 — a zero-readable vote shipped one reformatted draw, unlabelled

**Fix:** `backend/app/services/room_runner.py:5590-5634` tracks a new `_zero_readable_vote` flag,
set when `pm_self_consistency_samples > 1` and every draw/replacement in `_cands` is unparseable
but a raw draw exists (so the tail falls into the single-draw reformat path). After that path
produces `parsed` (`:5755-5776`), if `_zero_readable_vote` and `parsed is not None`, the verdict is
copied with `samples=_pm_samples`, `approve_votes=0`, and `reason` appended with an explicit
disclosure ("None of the N independent reads requested for this vote were machine-readable; this
is a single recovered read, not a vote."), plus a `room_pm_vote_zero_readable` warning log —
applied before the DEF384 shared decision tail, so the floor still sees the same `parsed` either
way; only the disclosure metadata changes.

**Test:** `::test_zero_readable_vote_is_labelled_not_a_silent_single_draw` — `samples=5`, a fake
gateway whose PM never parses on any draw but whose reformat retry recovers an APPROVE (matching
the auditor's own measurement: `reformat_calls=1`). Asserts `v.samples == 5`, `v.approve_votes ==
0`, and the disclosure text is present in `v.reason`.

```
cd backend && .venv/bin/python -m pytest tests/unit/test_retro_pm_floor_round2.py::test_zero_readable_vote_is_labelled_not_a_silent_single_draw -q -p no:cacheprovider
1 passed in 2.18s        EXIT=0
```

**Confirmed red pre-fix:** `v.samples` was `None` against the code before `_zero_readable_vote`
existed — the schema's own "self-consistency is off" meaning, false in this case; verdict action
was already `APPROVE` (an unlabelled single recovered draw), matching the auditor's probe.

**Mutation (reverted after):** short-circuited the disclosure block (`if False and
_zero_readable_vote and parsed is not None:`) → **1 failed** (`v.samples` back to `None` against
a still-`APPROVE` verdict). Restored; clean.

### MINOR-2 — a retracted draft APPROVE won on "first object wins"

**Fix:** `backend/app/services/llm_json.py`. New helper `_extract_second_decision` (a plain
brace-scan + `raw_decode` over the tail after the first parsed object — deliberately not the
DEF352/DEF398 recovery machinery, since this only answers "is there another decision-shaped
object here", never "recover a verdict from it"). In `extract_json_object`'s `raw_decode` branch
(`:176-196`), when the first decoded object has an `"action"` key, the tail is checked for a
second object; if one exists with a **different** `"action"`, the whole reply is now treated as
unparseable (`return None`) rather than returning the first (draft) object. Scoped strictly to
the `"action"` key so: (a) the pre-existing generic "first object wins" contract for non-decision
JSON is untouched (renamed test below), (b) `brief_engine.py`/`portfolio_finding.py`'s own
`extract_json_object` calls (payload shapes `overlay_addition`/`f1`/`f2`/`f4`, never `action`) are
unaffected, and (c) two objects with the SAME `action` (an echoed, not a conflicting, decision)
still resolve to the first, unchanged.

**Existing test updated:** `test_def398_pm_json_contract_break.py`'s
`test_the_first_object_wins_not_the_last` — this test's own two-object reply
(`{"action":"APPROVE"}` then `{"action":"REJECT"}`) is now EXACTLY the case MINOR-2 says must fail
safe, so per the auditor's own framing ("this is decision fidelity, not a floor bypass... the fix
is: fail safe when the tail contains a second object with a different action") the test's
expectation was wrong, not the fix. Split into three: (1) renamed to
`test_the_first_object_wins_when_the_pair_is_not_a_decision_conflict` using a non-`action` payload
to keep pinning the general DEF398 rule, (2) `test_two_conflicting_decisions_fail_safe_not_first_wins`
asserting the auditor's exact reply now returns `None`, (3)
`test_two_objects_with_the_SAME_action_are_not_a_conflict` pinning the "echoed decision" carve-out.

**New end-to-end test:** `test_retro_pm_floor_round2.py::test_a_retracted_draft_approve_fails_safe_not_ships_as_the_verdict`
— a fake gateway replaying the auditor's own probe text (`'Draft: {"action": "APPROVE",…} -- on
reflection I decline. {"action": "PASS",…}'`) through the real `RoomRunner.run()` at `samples=1`
(the single-draw path, matching the auditor's own reproduction). Asserts the verdict action is
never `APPROVE`.

```
cd backend && .venv/bin/python -m pytest tests/unit/test_def398_pm_json_contract_break.py tests/unit/test_retro_pm_floor_round2.py::test_a_retracted_draft_approve_fails_safe_not_ships_as_the_verdict -q -p no:cacheprovider
10 passed in ~5s        EXIT=0
```

**Confirmed red pre-fix:** both `test_two_conflicting_decisions_fail_safe_not_first_wins` and
`test_a_retracted_draft_approve_fails_safe_not_ships_as_the_verdict` failed against code before
the `"action" in decoded` check existed — `extract_json_object` returned the draft `APPROVE`
object, and the end-to-end run landed verdict `action='APPROVE'`.

**Mutation (reverted after):** short-circuited the new check (`if False and "action" in decoded:`)
→ both tests **failed** (2 failed) with the identical pre-fix symptom. Restored; clean.

### Suites run (targeted only — no bare `tests/unit/`)

Per the Architect's note mid-task: **the full backend unit suite was not run by this builder** —
another track's release-gate suite was running concurrently on the same Mac and bare
`tests/unit/` contends with its timing-sensitive tests. Only targeted files were run, every time,
which is what this section reports. The auditor re-runs the independent full suite per its own
BINDINGS, as it did in round 1 (melehost, sharded).

```
cd backend && .venv/bin/python -m pytest tests/unit/test_retro_pm_floor_round2.py tests/unit/test_room_runner.py tests/unit/test_safety_floor.py tests/unit/test_def384_vote_reaches_safety_floor.py tests/unit/test_sim_engine.py tests/unit/test_config_compose_parity.py -q -p no:cacheprovider
169 passed, 1 skipped in 106.62s        EXIT=0
```

Also run for collateral-damage coverage (every test file in the tree referencing
`extract_json_object`, `_build_room_sector_context`, `_respawn_run_from_row`, or
`sector_holdings`, beyond the task's own required list) and the 14-file set from the round-1
verdict's own targeted run:

```
cd backend && .venv/bin/python -m pytest tests/unit/test_cr026_sector_allocation.py tests/unit/test_cr098_room_analyst_pullback.py tests/unit/test_def110_outcome_liquidates.py tests/unit/test_def136_room_convene_does_not_block_loop.py tests/unit/test_def256_json_control_chars.py tests/unit/test_def258_pm_verdict_truncation.py tests/unit/test_def352_trailing_prose_after_json.py tests/unit/test_no_blocking_io_in_async_routes.py -q -p no:cacheprovider
106 passed        EXIT=0

cd backend && .venv/bin/python -m pytest tests/unit/test_safety_floor.py tests/unit/test_room_runner.py tests/unit/test_def384_vote_reaches_safety_floor.py tests/unit/test_def398_pm_json_contract_break.py tests/unit/test_def352_trailing_prose_after_json.py tests/unit/test_cr197_pm_self_consistency.py tests/unit/test_cr197_risk_officer.py tests/unit/test_cr197_size_envelope.py tests/unit/test_cr197_option_ladder.py tests/unit/test_cr201_risk_officer_room.py tests/unit/test_cr210_constraint_plumbing.py tests/unit/test_cr210_outcome_taxonomy.py tests/unit/test_cr210_room_wiring.py tests/unit/test_cr210_schemas.py tests/unit/test_retro_pm_floor_round2.py -q -p no:cacheprovider
341 passed        EXIT=0
```

(333 from the auditor's own round-1 list + 8: the 6 new tests in
`test_retro_pm_floor_round2.py` plus a net +2 in `test_def398_pm_json_contract_break.py`, which
had 1 test split into 3.)

Also re-ran the registers gate since I touched no register rows but the worktree brief requires
it be green regardless:

```
cd backend && .venv/bin/python -m pytest tests/unit/test_registers_no_drift.py tests/unit/test_p30_registers_name_things_that_exist.py -q -p no:cacheprovider
10 passed        EXIT=0
```

### Disposition per finding

| Finding | Disposition |
|---|---|
| MAJOR-1 | **Fixed.** Respawn now resolves the real portfolio snapshot before running; an unreadable snapshot fails the row loudly instead of defaulting. |
| MAJOR-2 | **Fixed.** Holdings-read failure and sector-resolver failure are now independent; only a genuine holdings-read failure blocks loudly (`None`), a sector-resolver-only failure degrades the sector cap alone. |
| MINOR-1 | **Fixed.** A zero-readable vote is now labelled (`samples`, `approve_votes=0`, disclosed reason) rather than shipping as an indistinguishable single-draw verdict. |
| MINOR-2 | **Fixed.** A second, conflicting decision in the tail now fails the whole reply safe rather than "first object wins" silently picking the draft. |

**Unresolved / not attempted this round:** none of the four findings. Everything the auditor
asked me to fix was fixed, tested from the auditor's own reproductions, and mutation-checked.
I did not re-verify the architect's round-1 "Attack surface" items the auditor's own verdict
already closed (compose parity, DEF383's `use_enum_values`, `risk_officer.py`'s absence of a
`Verdict`-construction path, CR210's `constraint_status` enum) — those were the auditor's own
round-1 findings-closed list, not open items handed to this fix pass, and re-deriving them was
outside the four items named in my task.

SUBMITTED: round 2
