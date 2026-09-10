# CR221 — slot 4: A2 debt split, D1 segment revenue, D2 geographic revenue (architect lane)

**Item:** `CR221-SLOT4` — one build slot of CR221 (Room data-demand sourcing). The CR's other
slots are research and measurement; this is the third code-bearing slot and the first that
reads a filing's own XBRL *instance* rather than the `companyfacts` frames.

**SCOPE:** chunk — slot 4 of CR221. The Definition-of-Done table is not owed for a chunk; the
CR-level DoD lives in the CR doc and closes with the CR.

**TIER: B** — one independent round, cap 3. Why B and not C: three new Room-sheet lines and a
rewritten persona sentence are user-facing once their flags flip, and the segment/geography
partition is a heuristic that decides what gets presented *as the filing's own figures*. Why
not A: every line is behind a flag that defaults False and is OFF on Alpha, there is no
migration, no new dependency, and the ingest writes into the existing `edgar_facts` table under
its own taxonomy (`ami`), so nothing a user sees has changed yet.

**SHA:** `64ee4051` on `main` (= `origin/main` at submission). The slot is four commits:

| commit | what |
|---|---|
| `aff954b6` | feat — instance parser, dimension resolvers, store rows, Room overlay, flag-gated render, persona/guard change, 73 tests |
| `0aa2ac03` | docs — CR doc "Slot 4 built" section, A4 closed ⛔ (not structural), `evidence/items.py` totals, row |
| `445f6a43` | chore — ingest names the successor-CIK case when a ticker has no 10-K (XOM) |
| `64ee4051` | DEF405 — promotion-gate record + postflight check. **Not in this lane's scope** (Tier C, self-verified, own row); listed because it sits inside the span and its origin is disclosed below |

**depends-on:** none.

## What and why

CR221 measured what the Room's twelve agents ask for and cannot get; 29 of its 127 request
lines (four items: A2, A4, D1, D2) wanted figures that `companyfacts` cannot carry because they
are *dimensional* — a debt total sliced by segment axis, revenue sliced by segment or geography
member. The extracted XBRL instance of the latest 10-K carries them, at
`https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{stem}_htm.xml`.

Three producers, one route:

- **`app/services/edgar_instance.py`** — parses an instance: contexts (period + `explicitMember`
  axes), units (**by `xbrli:unit` id**, then by measure — Deere's unit ids are opaque, the first
  cut read zero rows for DE and would have said "no dimensional debt"), facts.
- **`app/services/filing_dimensions.py`** — the resolvers. Debt split: captive-finance vs
  industrial members on the debt concepts, refused when only one side is present. Revenue
  partition: three tiers of revenue concept (external / operating-segment / bare), and within a
  tier the **largest member subset whose sum lands inside 90–110% of the same filing's
  consolidated revenue** (`_COVERAGE_BAND`), at least two members, at most twelve; single-member
  "partitions" are refused, filings older than 450 days are refused.
- **`scripts/ingest_edgar_dimensional.py`** — writes the resolved figures as `EdgarFactRow`s,
  taxonomy `ami`, tags `ami:CaptiveFinanceDebt:*`, `ami:IndustrialDebt:*`,
  `ami:SegmentRevenue:<tier>:<member>`, `ami:GeographicRevenue:<member>`,
  `ami:ConsolidatedRevenue:*`; the Room reads rows, never the network.
- **Room:** `_overlay_filing_dimensions` in `room_runner.py` always populates the profile and
  sets one `field_state` key per item (`debt_split`, `segment_revenue`, `geographic_revenue`);
  `_format_profile` in `room_prompts.py` renders each line only when its flag is on **and** the
  state is live. Flags `room_debt_split_enabled`, `room_segment_revenue_enabled`,
  `room_geographic_revenue_enabled` — default False, forwarded in `docker-compose.yml`.
- **Persona:** `content/agents/fundamentals_analyst.md` no longer says the split is
  unavailable; it says to use the sheet line where carried and never to split the blended total
  itself. The CR219 availability guard's R38 `_KNOWN_ABSENT` entry is retired and the new
  sentence is allowlisted as runtime-deference.
- **A4 (fixed vs floating mix)** closed ⛔: the instance carries it only as free text in the
  debt note, not as a dimensional fact — not structural, not sourced.

## The judgement calls I most want a second opinion on

1. **The partition band.** "Revenue by segment" is whichever member subset sums closest to the
   consolidated figure within 90–110%. CAT resolves on the *external* tier at 101.1% (the
   ops tier double-counts Financial Products); DE on the *operating* tier at 100.9% (its bare
   tier covers 87% and is refused); F at 100.0%; PCAR's only member covers 92% alone and is
   refused as a partition of one. The band is a heuristic — the auditor may want to argue it is
   too wide (a 90% subset presented as "the segments") or too narrow.
2. **Coverage is rendered, not hidden.** Each line states the members' sum against the
   consolidated figure so an agent can see a 101% or 91% partition for what it is. Whether that
   is enough, given CR038 (prompt text is not a control), is a fair question.
3. **Refusing one-member partitions** costs PCAR its segment line. I chose refusal over a line
   that says "Trucks: 92% of revenue" because the residual is not a segment.
4. **Debt split subtraction is refused, on purpose.** Consolidated minus captive would have
   given CAT 3,593 against a filed industrial figure of 10,713; the resolver requires both
   members to be filed.
5. **A4 closure** — I closed it rather than leaving it open-unsourced. Reopen if you read the
   debt-note text as parseable.

## Tests, command and observed output (measured on the committed SHA — DEF159)

Run in a detached worktree at `64ee4051` (`git worktree add --detach <path> 64ee4051`), so
the count is the committed tree's, not this checkout's dirty state:

```
cd <worktree>/backend && ../../backend/.venv/bin/python -m pytest \
  tests/unit/test_cr221_a2_debt_split.py \
  tests/unit/test_cr221_d1_d2_revenue_breakdown.py \
  tests/unit/test_cr219_availability_guard.py \
  tests/unit/test_config_compose_parity.py \
  tests/unit/test_def405_suite_verdict_gate.py \
  tests/unit/test_cr175_postflight.py \
  tests/unit/test_p30_registers_name_things_that_exist.py -q -p no:cacheprovider
195 passed, 1 skipped in 19.20s        (exit 0)
```

The two slot-4 files alone are 73 tests (68 passed + 5 failed under mutation M6 below). The
full suite ran at promotion time on `0aa2ac03` — see the disclosure under Governance.

## Revert-proof QA (mutation, run not reasoned)

Each mutation was applied to the detached worktree at `64ee4051`, the slot-4 tests plus the
availability guard were run, and the file reverted (`git status` clean after each). A pattern
that failed to apply would have been reported as NOT APPLIED, not as a survivor.

| # | mutation | result | killed by |
|---|---|---|---|
| M1 | `_MIN_PARTITION_MEMBERS = 2` → `1` (accept a one-member partition) | KILLED | `test_no_subset_inside_the_band_means_no_partition` |
| M2 | `unit=units.get(unit_ref) or _unit(unit_ref)` → `unit=_unit(unit_ref)` (drop the `xbrli:unit` map) | KILLED | `test_an_opaque_unit_id_resolves_through_the_unit_element` |
| M3 | `if (settings.room_debt_split_enabled` → `if (True` (render with the flag off) | KILLED | `test_the_flag_is_off_by_default_and_the_same_profile_renders_nothing` |
| M4 | both `field_state["debt_split"] = UNAVAILABLE` sites → `LIVE` (never report unavailable) | KILLED | `test_a_filer_with_no_lender_gets_no_block` |
| M5 | `MAX_ANNUAL_AGE_DAYS = 450` → `100000` (accept any age) | KILLED | `test_a_split_older_than_the_annual_bound_is_refused` |
| M6 | `_COVERAGE_BAND = (0.90, 1.10)` → `(0.0, 10.0)` (any subset is a partition) | KILLED (5) | `test_the_four_regions_beat_the_us_non_us_pair`, `test_the_four_segments_beat_their_own_aggregate`, `test_no_subset_inside_the_band_means_no_partition`, `test_a_bare_tier_that_covers_too_little_yields_nothing`, `test_geography_resolves_to_the_regions` |

## Live measurement, as it was run

Four filers, fetched live from the SEC on the Mac during the build (UA
`AMI Trade research (saiful.mazli@gmail.com)`), resolved through the same code path the ingest
uses, figures in $M from each filer's latest 10-K instance. Recorded in full in the CR doc,
section "Slot 4 built — A2, D1, D2"; the headline:

| filer | A2 debt split (captive / industrial) | D1 segment partition | D2 geography |
|---|---|---|---|
| CAT | 32,617 / 10,713 | external tier, 4 members, 101.1% of 67,589 | 4 regions, 100% |
| DE | UNAVAILABLE — no dimensional debt facts filed | operating tier, 100.9% of 45,684 (bare tier 87% refused) | 6 members |
| F | 141,417 / 21,919 | operating tier, 100.0% of 187,267 | 5 members |
| PCAR | captive only, 15,666 → refused (one side) | single member at 92% → refused | 3 members |

On Alpha (`ami_api_alpha`, tag `alpha-2026-09-11-1`): `scripts/ingest_edgar_dimensional.py`
over the 150-ticker Room universe wrote **2,736 rows for 146 of 150 tickers**; the four skips
are foreign filers/funds or a successor CIK with no 10-K yet (XOM maps to CIK 2115436,
ExxonMobil Holdings Corp — the reworded skip message in `445f6a43`). Container-side resolution
of CAT through the store was checked by hand and matched the Mac figures. PCAR is not in the
universe.

## Known limits, stated rather than left to be found

- All three flags are **OFF on Alpha**. The Room today renders none of these lines; §7 round 3
  (the `dims` arm, running from the Mac against vLLM as this is written) measures whether they
  change agent behaviour before any flip. That measurement is not evidence in this lane.
- The ingest is a script, not a schedule. Rows age; the 450-day bound refuses them rather than
  presenting a stale split, but nothing re-ingests on its own.
- The partition is a heuristic (call 1 above). It carries its own coverage on the line.
- `A4` closed as unsourced; `PCAR` gets no segment line; `DE` gets no debt split — all by
  design, all visible as `unavailable` in `field_state`.

## Governance

- CR221 row: `in_progress`; commit tags `(AT:R75 CR221)`; row and CR doc updated in `0aa2ac03`.
- **Disclosure — promotion gate.** `alpha-2026-09-11-1` (`445f6a43`) shipped after
  `preflight_suite.sh` was run through `| tail` in a background task; the task reported tail's
  exit 0 while the gate had printed `VERDICT: FAIL` on one docs-only check (a `../` too many in
  `DEF403.row.md`, fixed by the DEF403 lane at `9aff8fef`). The tag was left in place because
  the failing check has no runtime effect; the class was filed as **DEF405** and closed at
  `64ee4051` (gate writes `.deliveryos/suite_verdict.json`, postflight refuses a missing, stale,
  partial, mismatched or non-PASS record; 14 tests; P35 in `failure_patterns.md`). The tag also
  carries the DEF403 lane's `5ee0051f`/`f39dfc77`/`e4cbdc1e`, which are backend-only.
- Uncommitted in this checkout at submission (not part of this lane): §7 round-3 rig edits and
  result JSONs, which land with the round-3 write-up.

## Status at submission

Built, tested on the committed SHA, six mutations killed, ingested on Alpha, flags off.

SUBMITTED: round 1
--- files in the span (authoritative) ---
```
aff954b6 feat(CR221): A2/D1/D2 — debt split, segment and geographic revenue from the filing's own XBRL instance (AT:R75 CR221)
 backend/app/core/config.py                               |  13 ++
 backend/app/services/edgar_instance.py                   | 365 +++++++++++++++++++++++++++++++++
 backend/app/services/edgar_pit.py                        |  38 ++++
 backend/app/services/edgar_tags.py                       | 137 +++++++++++++
 backend/app/services/filing_dimensions.py                | 310 ++++++++++++++++++++++++++++
 backend/app/services/fundamentals.py                     | 104 ++++++++++
 backend/app/services/room_prompts.py                     |  35 ++++
 backend/app/services/room_runner.py                      |  92 ++++++++-
 backend/scripts/ingest_edgar_dimensional.py              | 275 +++++++++++++++++++++++++
 backend/tests/unit/test_cr219_availability_guard.py      |  92 ++-------
 backend/tests/unit/test_cr221_a2_debt_split.py           | 498 +++++++++++++++++++++++++++++++++++++++++++++
 backend/tests/unit/test_cr221_d1_d2_revenue_breakdown.py | 305 +++++++++++++++++++++++++++
 content/agents/fundamentals_analyst.md                   |   7 +-
 docker-compose.yml                                       |   6 +
 14 files changed, 2196 insertions(+), 81 deletions(-)
0aa2ac03 docs(CR221): slot 4 built — A2/D1/D2 measured on four filers, A4 closed as not structural (AT:R75 CR221)
 .../CR221_room_data_demand_sourcing.md                                | 114 ++++++++++++++++++++++++++++----
 .../CR221_room_data_demand_sourcing/evidence/items.py                 |   9 +--
 docs/forward_planning/_registry/CR221.row.md                          |   2 +-
 docs/forward_planning/cr_list.md                                      |   2 +-
 4 files changed, 108 insertions(+), 19 deletions(-)
445f6a43 chore(CR221): the dimensional ingest names the successor-CIK case when a ticker has no 10-K (AT:R75 CR221)
 backend/scripts/ingest_edgar_dimensional.py | 6 +++++-
 1 file changed, 5 insertions(+), 1 deletion(-)
```

---

# Round 2 — the three round-1 findings, fixed

**SHA:** `48865a32` on `main` (= `origin/main`), one commit on top of `64ee4051`. All three
findings are accepted as written; none is contested. The five rulings on the judgement calls
are noted with thanks — call 2 in particular (CR038 is about instructions, this is a datum).

## MAJOR-1 — the aggregate filter now has the test that reaches it

`test_an_aggregate_beside_one_segment_is_refused_not_rendered_at_100_percent` in
`backend/tests/unit/test_cr221_d1_d2_revenue_breakdown.py` builds the case the filter's own
comment fears and the auditor ran: `us-gaap:ReportableSegmentsMember` at 92% beside
`acme:WidgetsMember` at 8% on the external tier, against the fixture's consolidated total. It
asserts two things one layer up from `select_partition`: `_members_at` returns only the
segment, and `resolve_segment_revenue` refuses (no ops/bare tier to fall through to). The
auditor's reading is right that render-time is the only filter in the system — that is the
design (the store keeps what the filer tagged; the resolver decides what is a partition) — and
it is now a tested control rather than a present one.

## MINOR-1 — the row names the pair that reconciles

`CR221.row.md` now reads: *"its two noncurrent column cells — Financial Products $20,018M +
Machinery, Power & Energy $10,678M — sum to the non-dimensional `LongTermDebtNoncurrent`
$30,696M to the dollar; the industrial figure is read, never derived"*. `cr_list.md`
regenerated.

## MINOR-2 — the recovery is in the script's own docstring

`ingest_edgar_dimensional.py`: a partial run and an honest absence render identically; they
are told apart from the store (no `ami:` rows at all vs. `ami:ConsolidatedRevenue:*` rows
without `ami:SegmentRevenue:*`), a re-run without `--force` fills the gaps because a stored
filing is skipped by accession, and `--force` re-reads a filing already present.

## On `origin/main`

From the main checkout the ref resolves and equals HEAD after every push in this lane; the
auditor's detached worktree lacks the remote-tracking ref, which is how that worktree was
created, not a repository state. Nothing to fix on the remote.

## Measured on the committed SHA `48865a32` (fresh detached worktree, DEF159)

```
pytest test_cr221_a2_debt_split.py test_cr221_d1_d2_revenue_breakdown.py \
       test_cr219_availability_guard.py test_config_compose_parity.py \
       test_p30_registers_name_things_that_exist.py
156 passed, 1 skipped in 14.58s        (exit 0)

U-M1  `if _AGGREGATE_MEMBER.search(member):` → `if False:`   (applied, run, reverted)
FAILED tests/unit/test_cr221_d1_d2_revenue_breakdown.py::test_an_aggregate_beside_one_segment_is_refused_not_rendered_at_100_percent
1 failed, 28 passed in 2.81s
```

SUBMITTED: round 2

---

# Round 3 — MAJOR-2 dispositioned: fixed here, and the gate run this time

**SHA:** `083b8918` on `main` (= `origin/main`), one commit on top of `48865a32`. The round-2
header said "the three findings"; four were filed. MAJOR-2 was not contested and not
forgotten on purpose — the round-1 section carried a full-suite placeholder when I read it and
gained MAJOR-2 after; that is my reading discipline to fix, not the auditor's filing. It is
disposed here as option 1, the fix, because `64ee4051` is my own commit.

## MAJOR-2 — fixed at its source, and the fixture made loud

Two changes, one commit (`083b8918`, tagged DEF405 because that is the commit that broke it):

1. **`test_def405_suite_verdict_gate.py`** — `test_the_record_lives_where_git_ignores_it` no
   longer reads the root ignore file by name. It asks git: `git check-ignore -q
   .deliveryos/suite_verdict.json` must exit 0. That is the property the test meant (the gate
   must not dirty the tree it measures), and the file's basename no longer appears in
   `backend/tests/`, so `mobile/ios/.gitignore` is unattributable again.
2. **`test_cr216_test_selection.py`** — `_an_unnamed_tracked_nonpython_file()` now scans
   `backend/tests/**/*.py` for each candidate's basename, skips a candidate any test names, and
   when none survives raises with the list *"<file> is named by <test>"*. The next collision
   fails as a named fixture error, not as two inverted selector tests. The selector's
   basename attribution is unchanged — the auditor is right that path-aware attribution is
   the real fix, and that is CR216's own change, recorded here and not made in this lane.

The CR222 lane found the same red independently at 18:33Z (their branch = main + slices
touching neither file) and was told the fix SHA.

## The full suite, run as the gate, on the committed SHA

`preflight_suite.sh` run **bare** (no pipe, no `tail`) in a fresh detached worktree at `083b8918`,
verdict read from the DEF405 record the gate wrote, not from the task's exit code:

```
{
  "sha": "083b89187f12bbeb11db38f324d0f9eac9368c11",
  "verdict": "PASS",
  "target": "backend/tests/unit/",
  "at": "2026-09-10T18:52:57Z",
  "passed": 6470,
  "failed": 0,
  "errors": 0
}
```

Targeted files at the same SHA, same worktree:

```
test_cr216_test_selection.py test_def405_suite_verdict_gate.py test_cr221_a2_debt_split.py
test_cr221_d1_d2_revenue_breakdown.py test_cr219_availability_guard.py
165 passed in 37.50s        (exit 0)
```

## On `origin/main` — correction accepted

The auditor ran the failing `git fetch` in the main checkout, not a worktree; my round-2
diagnosis was wrong and is withdrawn. Conclusion unchanged: transient, resolves now, nothing on
the remote.

SUBMITTED: round 3

