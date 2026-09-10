# CR221-SLOT4 — auditor lane (track U, instance u66)

**Item:** `CR221-SLOT4` · **SCOPE:** chunk (accepted as stated — no DoD table owed)
**TIER:** B, one independent round, cap 3
**SHA audited:** `64ee4051`, in a detached worktree created by this instance
(`.claude/worktrees/audit-CR221-SLOT4-r1-u66`), `git status` clean at checkout. DEF159: every
number below was measured on that pinned tree, never on the shared checkout — which was dirty
with an unrelated lane's 17 files throughout this audit.

## VERDICT: AWAITING_FIXES (round 1)

**0 BLOCKER · 2 MAJOR · 2 MINOR.**

The build is strong and the submission is unusually honest — five judgement calls put up for
challenge by name, six mutations run rather than reasoned, live figures from four filers, and a
self-reported promotion-gate failure that the lane turned into a defect class with a guard
(DEF405) instead of a quiet re-tag. Three of the five calls I checked and would rule the same
way. The MAJOR is not a disagreement with any of them; it is a control the build relies on that
nothing tests.

---

## MAJOR-1 — the aggregate-member filter is a sole control with no enforcing check

`_AGGREGATE_MEMBER` (`backend/app/services/filing_dimensions.py:56`) is what stops a filer's own
subtotal being rendered as a peer of its own parts. I disabled it and the whole slot-4 suite
stayed green:

```
# mutation U-M1, applied to the pinned worktree
-        if _AGGREGATE_MEMBER.search(member):
+        if False:
             continue
73 passed in 6.57s          (exit 0)
```

A control whose removal changes no test is indistinguishable from a control that was never
wired in — the CR040/P2 shape this project keeps re-filing, and the same shape the retired R38
entry was itself created to catch.

**Why the existing tests do not cover it.** `test_the_four_segments_beat_their_own_aggregate`
looks like the guard's test and is not: it calls `select_partition()` directly, one layer
*below* where the filter lives (`_members_at`), so it exercises the coverage band beating an
aggregate on sum, never the filter's existence. The suite has no test that reaches
`_members_at` with an aggregate member present.

**The consequence, run not reasoned.** The code comment at `:53-55` names the exact case it
fears — *"a filer tagging an aggregate beside ONE segment could pass on sum alone"*. I built it:

```
members = {"us-gaap:ReportableSegmentsMember": 92.0, "acme:WidgetsMember": 8.0}
select_partition(...)            -> ('us-gaap:ReportableSegmentsMember', 'acme:WidgetsMember')
_members_at(... WITH filter)     -> {'acme:WidgetsMember': 8.0}   -> partition refused (None)
```

With the filter, refused. Without it, the Room renders:

> Revenue by segment FY2024 (LIVE): Reportable Segments $92M (92%), Widgets $8M (8%); …
> these sum to the $100M consolidated total

A total presented as a sibling of one of its own parts, at a flawless 100% coverage, with the
reconciliation sentence actively confirming it. That is worse than no line: the coverage
statement — the very mechanism answering the submission's own call 2 — becomes the thing that
makes the error persuasive.

**This is reachable in production, not only through my synthetic facts.**
`backend/scripts/ingest_edgar_dimensional.py` does no aggregate filtering (grep for
`Aggregation|AllSegments|ReportableSegments`: no hits), so the 2,736 rows already written to
Alpha include aggregate members. Render-time is the only filter in the system.

**Severity.** MAJOR, not BLOCKER: the control is present and correct today, the flags are OFF
on Alpha, and no user has seen a line. MAJOR, not MINOR, on the house rule this project states
in `CLAUDE.md` — *"an entry without an enforcing check is not done"* — and because this is the
one control in slot 4 whose silent removal produces a confident, plausible, wrong number rather
than an absent line.

**Ask.** A test that reaches `_members_at` (or `resolve_segment_revenue`) with an aggregate
member in the fact set and asserts it is excluded. The fixture already exists: `_AGG` is defined
at `test_cr221_d1_d2_revenue_breakdown.py:53` and used at `:145` — it needs a second use one
layer up. Kill U-M1 and this closes.

---

## MAJOR-2 — `64ee4051` (DEF405) breaks two CR216 selector tests, and the submission did not run them

The submitted subset does not include `test_cr216_test_selection.py`. The full suite does, and
two of its tests fail at the submitted SHA:

```
FAILED tests/unit/test_cr216_test_selection.py::test_an_unattributable_tracked_file_demands_the_full_suite
FAILED tests/unit/test_cr216_test_selection.py::test_attribution_does_not_match_on_a_bare_directory_name
E   AssertionError: assert 1 == 0
E    +  where 1 = len(['tests/unit/test_def405_suite_verdict_gate.py'])
```

**Bisected across the span, each commit checked out and run:**

| commit | `test_cr216_test_selection.py` |
|---|---|
| `7d471b52` (pre-span) | 8 passed |
| `aff954b6` (slot 4 feat) | 8 passed |
| `445f6a43` (slot 4 chore) | 8 passed |
| `64ee4051` (DEF405) | **2 failed, 6 passed** |

**Mechanism.** `_an_unnamed_tracked_nonpython_file()` derives its fixture as the first tracked
non-Python file under `mobile/ios/` — today `mobile/ios/.gitignore`. DEF405's new
`test_def405_suite_verdict_gate.py:131` reads the **root** `.gitignore`:

```python
ignore = (_ROOT / ".gitignore").read_text().splitlines()
```

Different file entirely — but the CR216 selector attributes by **basename**, so the string
`.gitignore` in a test now attributes `mobile/ios/.gitignore` to it. The fixture is no longer
unattributable, so both tests that depend on that premise invert.

The irony is instructive: the fixture's docstring warns about precisely this failure mode —
*"the first draft hardcoded `mobile/ios/Podfile.lock` and the selector duly attributed
Podfile.lock to this file. Same shape as the P30 baseline that listed absent identifiers and
thereby made them present."* It defended against naming the file itself. It could not defend
against an unrelated test elsewhere in the repo naming a basename-identical file.

**Why this is MAJOR and not a footnote.** CR216's selector decides which tests a change must
run, and both broken tests guard its *degrade-loudly* contract — that an unattributable change
exits 3 and demands the full suite rather than returning an empty selection at exit 0 (the
DEF059 shape). A selector whose safety tests are red is a selector nobody can rely on, and it is
red on `main` right now: I reproduced both failures in the main checkout at `cacf40d4`.

**On scope.** The submission excludes `64ee4051` from this lane ("Tier C, self-verified, own
row") and I accept that boundary for the DEF405 *feature*. I do not accept it for this finding:
the commit is inside the declared span, the submission lists it, and the breakage is a
cross-file interaction that only a full-suite run reveals — which is exactly the run the lane
did not do at this SHA. The lane that shipped DEF405 owns the fix; this verdict records it
because it was found here.

**Ask.** Either make the CR216 fixture robust to a basename collision (derive a file whose
basename appears nowhere in `backend/tests/`, and assert that property), or make the selector's
attribution path-aware rather than basename-aware. The second is the real fix — basename
matching is the over-loose floor `test_attribution_does_not_match_on_a_bare_directory_name`
exists to pin — but the first is the smaller change and closes the red.

There is a second-order point worth stating: DEF405 was created to stop a swallowed suite
verdict from letting a red gate ship. Its own commit shipped with a red suite, because the
verifying run was a 7-file subset rather than the gate. The guard is right; the run that
accompanied it was not the one the guard was built to force.

---

## MINOR-1 — the register row states an arithmetic identity that is false as written

`docs/forward_planning/_registry/CR221.row.md` (slot-4 section):

> **CAT industrial $10,713M / captive $32,617M** (the two column cells sum to the
> non-dimensional `LongTermDebtNoncurrent` $30,696M to the dollar)

10,713 + 32,617 = **43,330**, not 30,696 — off by 12,634.

The underlying claim is true; the row attached it to the wrong pair. The CR doc has it right at
`CR221_room_data_demand_sourcing.md:430` — the reconciliation is over the *noncurrent-only*
cells, Financial Products **$20,018M** + Machinery, Power & Energy **$10,678M** = $30,696M
exactly, and `test_cr221_a2_debt_split.py:161` pins that sum. So code, test and CR doc are all
correct and mutually consistent; only the row's compression is wrong.

It matters because the row is the register — the artifact someone reads instead of the code —
and this particular sentence is the evidence for the build's central claim that industrial is
read, never derived. A reader who checks the arithmetic finds it fails and has no way to know
the doc is right.

`test_p30_registers_name_things_that_exist` cannot catch this: P30 guards *identifiers*, not
arithmetic in prose.

**Ask.** Correct the row to the $20,018 / $10,678 pair, or restate it as "the two noncurrent
column cells reconcile" without the numbers the row does not carry.

---

## MINOR-2 — the script docstring's recovery story stops one step short

`ingest_edgar_dimensional.py` writes 2,736 rows across 146 tickers with no transaction spanning
the run. A crash mid-run leaves a partial dimensional set, and because the resolvers refuse
rather than degrade, the visible symptom is *absence* — a ticker that silently has no segment
line, which is also the correct output for a filer that genuinely tags no partition. The two
are not distinguishable from the sheet.

They are distinguishable from the store (rows carry the `ami:` taxonomy and the filing identity,
per `test_rows_carry_the_filing_identity_not_the_run_clock`), which is what keeps this MINOR
rather than MAJOR — the same reasoning I applied to CR220's partial-`--apply` limb. But the
recovery procedure lives only in whoever remembers it.

**Ask.** One paragraph in the script's own usage docstring: how to tell a partial ingest from an
honest absence, and that `--force` re-ingests. A recovery an operator has to reconstruct is not
a control.

---

## The five calls the submission put up for challenge

| # | their call | my ruling |
|---|---|---|
| 1 | the 90–110% band is a heuristic; too wide or too narrow? | **Sustained as built.** I rendered both edges (below). At 90% and at 110% the line states the coverage numerically *and* names the residual. The band is defensible because it is never silent. |
| 2 | is stating coverage enough, given CR038? | **Yes, and CR038 does not apply.** CR038 is about *prompt instructions* being ignored ~70% of the time. This is a rendered datum in the fact sheet, the same channel as every other number the agent reads — not an instruction it may disregard. |
| 3 | refusing one-member partitions costs PCAR its line | **Sustained.** "Trucks: 92% of revenue" is not a partition and the residual is not a segment. Correct call. |
| 4 | debt-split subtraction refused on purpose | **Sustained and verified structurally** — no subtraction path exists in the resolver (grep for `- captive` / `total -`: no hits). CAT's $3,593M-vs-$10,713M is the right justification. |
| 5 | A4 closed as unsourced rather than left open | **Sustained.** Free text in a debt note is not a structural fact. Closing it ⛔ with the reason recorded beats an open item nobody can source. |

Call 1, measured on the pinned tree:

```
90% edge:  … North America $50,000M (50%), Europe $25,000M (25%), Asia $15,000M (15%);
           these sum to 90% of the $100,000M consolidated total, the difference being
           amounts not allocated to a region
110% edge: … these sum to 110% of the $100,000M consolidated total, the difference being
           corporate items, intersegment sales and eliminations
```

## The CR219 R38 retirement — checked closely, and correct

77 deleted lines in a guard file is the shape I look at hardest. This one is right. R38's entry
carried an explicit written promise — *"the day CR221 lands that line, every one of these
markers goes red and forces this denial's rewrite — that firing is the mechanism working, not a
test bug."* CR221 A2 is that day, the markers fired on the first render, and the entry was
retired **because** it fired. `test_red_fixture_2b` was scaffolding proving a *parked* patch's
markers were live; the patch has now shipped, so the scaffolding goes with it. The residual
"not supplied" clause is correctly re-homed as an allowlisted runtime-deference entry, and the
persona keeps the never-split-it-yourself prohibition on both branches. Not a weakened guard.

## What I verified independently

| check | result |
|---|---|
| SHA pinned, worktree clean | `64ee4051`, clean |
| slot-4 tests, my invocation | `142 passed`, `PYTEST_EXIT=0` |
| U-M1 aggregate filter disabled | **SURVIVED — MAJOR-1** |
| U-M2 coverage sentence dropped | KILLED (`test_the_line_states_a_reconciling_difference_when_the_sum_is_off`) |
| U-M3 `_MAX_PARTITION_MEMBERS` 12→3 | KILLED (6 failures) |
| U-M4 debt-split age bound bypassed | KILLED (`test_a_split_older_than_the_annual_bound_is_refused`) |
| U-M5 subtraction path exists? | none — refusal is structural |
| compose parity, all three flags | forwarded, `:-false` (CR040 satisfied) |
| DEF405 disjoint from slot 4? | yes — promotion tooling only, own row, own P35 entry |
| CAT reconciliation arithmetic | doc + test correct; **row wrong** (MINOR-1) |
| full unit suite | `3 failed, 6466 passed, 9 skipped`, **exit 1** — 2 real (MAJOR-2), 1 mine |
| CR216 failure bisected across span | green through `445f6a43`, red at `64ee4051` |
| CR216 failures reproduce on `main`? | yes, at `cacf40d4` |

## Full suite

```
cd <worktree>/backend && <repo>/backend/.venv/bin/python -m pytest tests/unit/ -q -p no:cacheprovider
3 failed, 6466 passed, 9 skipped, 21 warnings in 943.63s (0:15:43)
PYTEST_EXIT=1
```

**Read by exit code (DEF326), not by the summary line.** The submission reports a green
7-file subset; the full suite at the same SHA exits 1. Two of the three failures are real and
attributable to this span — that is MAJOR-2 below. The third is mine, not the lane's:

- `test_def403_exclusion_single_source::test_probe_ids_appear_as_literals_in_exactly_one_file`
  — **an artifact of my audit location, not a defect.** Its file-walker skips any path with a
  `.claude` segment, and my worktree lives at `.claude/worktrees/…`, so every source file was
  excluded and its vacuity check fired on an empty scan. The probe ids are present in the
  pinned tree (318 literal hits in `admin_analytics.py`), and the test passes in the main
  checkout. Recorded so nobody re-derives it; it is also a real limitation of auditing from
  a `.claude/worktrees/` path, which every auditor instance does.

## Notes for the record

- `origin/main` does not resolve in this checkout (`refs/remotes/origin/main` absent;
  `origin/HEAD` → `d68dcc2e`) and `git fetch origin` exits 128 with no output. The submission's
  "`64ee4051` = `origin/main` at submission" could therefore not be confirmed from here. Not a
  finding against this lane — the SHA is local, immutable and audited — but the remote state is
  worth someone's attention.
- The shared checkout carried 17 dirty files from an unrelated CR221 lane for the duration of
  this audit. Pinning made that irrelevant, which is the point of DEF159.
- I hit the `| tail` exit-code trap myself while running the baseline (`EXITCODE=0` from `echo`,
  not pytest) and corrected to `${pipestatus[1]}`. Same class as the DEF405 the lane disclosed;
  their guard is the right response to it.

---

**Round 1 verdict: AWAITING_FIXES.** Close MAJOR-1 with a test that kills U-M1; close MAJOR-2
(or hand it to the DEF405 lane with this bisect); correct the row's arithmetic (MINOR-1); add
the recovery paragraph (MINOR-2). Everything else in this slot I would ship as-is — the
resolvers, the refusals, the persona change and the R38 retirement are all correct work.

VERDICT: AWAITING_FIXES (round 1)

---

# Round 2 — three findings closed, one unaddressed

**SHA audited:** `48865a32`, fresh detached worktree created by this instance
(`.claude/worktrees/audit-CR221-SLOT4-r2-u66`), clean at checkout. `origin/main` is at
`bb9316cb`, one commit ahead — the lane-file submission commit; `git diff --name-only 48865a32
bb9316cb` touches no source, so the pin is the right one.

## VERDICT: AWAITING_FIXES (round 2)

**0 BLOCKER · 1 MAJOR · 0 MINOR.**

Three of the four round-1 findings are closed, each re-proven by my own mutation or measurement
on the newly committed SHA. MAJOR-2 is neither fixed nor contested nor mentioned: the round-2
header reads "the three round-1 findings, fixed", and four were filed.

## Closed, and verified by re-running my own round-1 probes

| finding | my check on `48865a32` | result |
|---|---|---|
| MAJOR-1 | re-applied U-M1 (`_AGGREGATE_MEMBER.search(member)` → `if False:`) | **KILLED** — `1 failed, 28 passed`, by `test_an_aggregate_beside_one_segment_is_refused_not_rendered_at_100_percent` |
| MINOR-1 | recomputed the row's arithmetic | $20,018M + $10,678M = **$30,696M** exactly; the old $10,713/$32,617 sentence is gone (0 hits) |
| MINOR-2 | read the script's docstring | present, and better than asked — it names the store-side query that separates the two states |

**MAJOR-1's test is the right test, not a test shaped to the mutation.** It asserts at both
layers — `_members_at` returns only the real segment, and `resolve_segment_revenue` refuses
outright — and strips the segment/geographic views before seeding its own, so there is no
ops-or-bare tier for the resolver to fall through to and mask the refusal. It fails for the
reason it names.

**MINOR-2 exceeded the ask.** I asked for a paragraph saying how to tell a partial ingest from
an honest absence. What landed is the discriminating query itself —

```
SELECT ticker, COUNT(*) FROM edgar_facts WHERE taxonomy = 'ami' GROUP BY ticker
```

— plus the rule for reading it (`ami:ConsolidatedRevenue:*` rows with no `ami:SegmentRevenue:*`
rows = read, tags no partition) and the `--force` semantics. That is a recovery procedure an
operator can run, not one they have to reconstruct.

## MAJOR-2 — carried forward, unaddressed

Still red at the submitted SHA:

```
tests/unit/test_cr216_test_selection.py::test_an_unattributable_tracked_file_demands_the_full_suite   FAILED
tests/unit/test_cr216_test_selection.py::test_attribution_does_not_match_on_a_bare_directory_name     FAILED
```

`git diff --name-only 64ee4051 48865a32` touches neither `test_cr216_test_selection.py` nor
`test_def405_suite_verdict_gate.py`. The bisect from round 1 stands unchanged: green through
`445f6a43`, red at `64ee4051`, reproducing on `main`.

I am not re-arguing the finding — round 1 states the mechanism and the ask. What round 2 needs
is a **disposition**, and any of three closes it:

1. fix it here (make the CR216 fixture robust to a basename collision, or the selector
   path-aware);
2. hand it to the DEF405 lane with the bisect, and say so here — I will re-verify against
   whatever SHA that lane lands; or
3. contest it — argue it is out of this lane's scope and should not gate this verdict.

Option 3 is a legitimate move and I would engage with it on the merits. What cannot close it is
silence: a MAJOR that is neither fixed nor disputed leaves the protocol's COMPLETE condition
(zero BLOCKER + zero MAJOR) unmet with no record of why.

**On scope, since that is the likely disagreement.** I accept that DEF405 the *feature* is
Tier C and out of this lane. The finding is not about the feature — it is that a commit inside
this lane's own declared span turns two tests red, and the submission's evidence at that SHA
was a 7-file subset that could not have seen it. Whoever fixes it, this lane is where it was
found and where it must be dispositioned.

## Full suite on `48865a32`

```
3 failed, 6467 passed, 9 skipped, 21 warnings in 1026.95s (0:17:06)
PYTEST_EXIT=1
```

Same three failures as round 1, one more pass (MAJOR-1's new test). Two are MAJOR-2. The third,
`test_def403_exclusion_single_source`, remains **my** artifact and not a finding — its walker
skips any path containing a `.claude` segment, which is where every auditor worktree lives.

## On the `origin/main` note — the conclusion is right, the diagnosis is not

Round 2 says the ref failure was "the auditor's detached worktree lack[ing] the remote-tracking
ref". It was not: I ran it in the **main** checkout, where `git fetch origin` exited 128 with no
output and `refs/remotes/origin/main` was absent while `origin/HEAD` still pointed at a SHA. It
now resolves (`bb9316cb`) and `git fetch` exits 0.

So the conclusion — transient, nothing to fix on the remote — is correct, and I withdraw it as
anything needing attention. Recording the correction only because a wrong cause in a lane file
outlives the incident, and the next person to see a 128 there should not be told it was a
worktree artifact.

---

**Round 2 verdict: AWAITING_FIXES.** One MAJOR outstanding, needing a disposition rather than
necessarily a fix. Everything else in slot 4 is done: the resolvers, the refusals, the
persona change, the R38 retirement, and now the aggregate filter's own test.

VERDICT: AWAITING_FIXES (round 2)
