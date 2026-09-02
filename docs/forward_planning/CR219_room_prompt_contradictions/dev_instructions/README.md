# CR219 dev instructions — how to build the 61 register items

This folder turns [`../issue_register.md`](../issue_register.md) (61 rows, R1–R61) into
build instructions a coding session can execute. Written 2026-09-02 by the Fable review
track after Saiful ruled the register's six open forks (see
[`DECISIONS_2026-09-02.md`](DECISIONS_2026-09-02.md)). **Every register row is covered:
each maps to exactly one work-package (WP) file below, and each WP file carries per-row
instructions.** The register + this folder are the complete handoff.

## Who executes this

Coding is done by **Haiku / Sonnet / Opus worker sessions**, not by the review track.
Routing and verification rules:

| WP | Content | Model | Why |
|---|---|---|---|
| WP09 | Docs corrections | Haiku ok | Mechanical, cheap to verify by grep |
| WP01, WP03, WP04, WP05, WP06 | Persona edits, overlay, data fields | **Sonnet** | Standard coding with tests |
| WP02 (guard), WP07 (harness), WP08 (verdict pipeline) | Load-bearing control + design-heavy | **Opus** (or Sonnet with explicit review) | The guard is the control that makes everything else stick |

**Never accept a worker's word for completion** (standing rule: economy-tier workers
fabricate "done/pushed/green" and even status tokens). Acceptance for every WP =
(1) `backend/.venv/bin/pytest backend/tests/unit/ -q` exit 0, run by the acceptor,
(2) `git log`/`git diff` shows the claimed commits touching only the claimed files,
(3) the WP's own acceptance checks pass. Plain `pytest` on PATH resolves to a
`structlog`-less env and fails collection — always use the venv binary.

## Authority order

When sources disagree: **DECISIONS_2026-09-02.md > issue_register.md dispositions >
reviewer docs**. Reviewer docs (`../kimi/`, `../antigravity/`, `../GLM/`, `../QWEN/`,
`../fable/`) are drafting material — use them where a WP points at them, but a register
ruling always wins. Known trap: do NOT copy Antigravity's social-analyst rewrite (R6
rejects it — it grants a false sentiment-baseline claim).

## House rules that bind every commit (from CLAUDE.md, enforced here)

- **Pathspec commits only**: `git commit -m "…" -- <files>`. Never bare `git commit`,
  `-am`, or `git add -A` — the checkout is shared and will sweep other lanes' work.
- **Commit tag**: `(AT:R75 CR219)` on every code commit. Docs-only commits may use plain
  `(AT:R75)`.
- **Stay in your lane**: touch only files a WP names. Never edit other reviewer folders.
  `../issue_register.md` Build boxes: flip `☐`→`☑` in the same commit that closes a row.
- **Degrade loudly (CR040)**: every new config setting must be forwarded in
  `docker-compose.yml`'s `api-alpha` block (`test_config_compose_parity.py` enforces);
  every new data field fails visibly when its fetch is absent — never a silent fallback.
- **CR038**: prompt instructions are not controls (~70% ignored under pressure). For every
  persona-prose fix, the guard/test added in the same commit is the actual guarantee.
- **The AI is named AMI** in anything a user might read; "LLM" is fine in code/tests.
- **New IDs**: never mint a `DEF###`/`CR###` yourself — ask the Architect (single
  ID-minter rule). Relevant to WP08's R43 and WP06's R38-split contingency.
- **Mac is pure editor**: no backend, no DB, no Docker here. Unit tests only; anything
  live goes through `/promote-to-alpha` after Saiful's go.
- File headers: every new file opens with a docstring/comment saying what it is and why.

## Build order

```
WP09 (docs corrections — do first, they fix facts other WPs cite)
  └─► WP02 guard skeleton + red fixtures ──► WP01 personas (one agent per commit,
        guard entries land in the same commit)
            └─► WP03 instruction fights ──► WP04 R23/R24 (surfaces)
                  └─► WP05 primary_goal + mandate fields
                        └─► WP06 data additions (R39: only after the fixes above)
                              └─► WP04 R21 closes (overlay demand ↔ shipped field)
WP07 harness — start any time in parallel; must exist before WP07's experiments
               and before AC4's trailing measurement
WP08 verdict pipeline — after WP02; R50/R51 independent of WP06
```

## Row → WP index (all 61)

| Rows | File | One-line action |
|---|---|---|
| R1–R7 | [WP01_personas_class_a.md](WP01_personas_class_a.md) | Fix the 8 false denials, keep + register the 3 true ones |
| R8–R14, R22, R44, R61 | [WP02_guard.md](WP02_guard.md) | Build guard v2: truth-checked, whole-file, overlay-mapped, collision-marked, exhaustive |
| R15–R20 | [WP03_instruction_fights.md](WP03_instruction_fights.md) | Resolve the six instruction-vs-instruction collisions |
| R21, R23, R24 | [WP04_surfaces.md](WP04_surfaces.md) | Overlay↔field alignment, downstream brief acknowledgment, 1-on-1 lane gate |
| R25, R26, R56 | [WP05_primary_goal.md](WP05_primary_goal.md) | Wire `primary_goal` + the two dead mandate fields as weighted guidance |
| R33–R40 | [WP06_data_additions.md](WP06_data_additions.md) | Ship the free fields + multiples + debt split + revisions, provenance-first |
| R29–R32, R46, R47, R48, R54 | [WP07_harness_measurement.md](WP07_harness_measurement.md) | Build the merged golden-set harness; run the two experiments |
| R43, R49–R52 | [WP08_verdict_output.md](WP08_verdict_output.md) | PM floor-parity, scoreboard, outage honesty, kill-criterion, DEF filing |
| R27, R28, R41, R42, R45 | [WP09_docs_corrections.md](WP09_docs_corrections.md) | Fix stale facts; reconcile the target-architecture statements |
| R53, R55, R57–R60 | [PARKING_LOT.md](PARKING_LOT.md) | Parked — do NOT build in CR219 |

## Definition of done (whole CR)

1. All buildable rows flipped `☑` in `../issue_register.md` (parked rows stay `☐` with
   their PARKING_LOT pointer).
2. `backend/.venv/bin/pytest backend/tests/unit/ -q` green, including the new guard.
3. `backend/.venv/bin/python ../evidence/analysis/verify_citations.py` exit 0 (persona
   edits move line numbers — re-run after every WP01/WP03 commit).
4. The WP02 guard passes on HEAD and its red fixtures fail when planted.
5. AC4 (citation-rate re-measurement on Alpha traffic) is **scheduled, not gating** —
   logged in the CR folder ~1–2 weeks after promote (R30).
6. Promotion to Alpha only via `/promote-to-alpha`, after Saiful's go.
