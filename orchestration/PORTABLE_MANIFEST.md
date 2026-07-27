<!--
PORTABLE_MANIFEST.md — the authoritative copy list for standing this orchestration protocol up in
another repository. PORTABLE CORE: copy this file too. It answers exactly one question per file:
does it copy verbatim, get written once for the new project, or never leave this repo?
-->

# Portable manifest — what to copy into a new repo

Three tiers. **A** copies byte-for-byte. **B** is written once per project. **C** never leaves the
repo it was created in.

The split has one invariant, and every file in tier A is checked against it: **a portable file names
no project, no host, no person, no path outside this tree, and no work-item id.** A rule whose only
justification is something that happened here states the rule and points at BINDINGS for the
evidence. If you find a project detail in a tier-A file, that is a bug in the split — move it to
BINDINGS rather than preserving it.

## Tier A — copy verbatim (16 files)

| File | What it is |
|---|---|
| `PORTABLE_MANIFEST.md` | this file |
| `README.md` | map of the two layers; start here |
| `ROLES.md` | the four-role model + the load-bearing rules |
| `DEFINITION_OF_DONE.md` | the portable DoD questions (answers live in tier B) |
| `history/README.md` | what the durable-memory tree is for |
| `dispatch/DISPATCH_PROTOCOL.md` | Architect ↔ instance contract, tokens, state table, the gate |
| `dispatch/dispatch.sh` | state deriver + watcher (`state` / `inbox` / `architect` / `inst <id>`) |
| `dispatch/rotate_trail.py` | ledger retention, ledger-agnostic |
| `dispatch/loop_prompts/ARCHITECT.md` | Architect role prompt |
| `dispatch/loop_prompts/AUDITOR.md` | Auditor role prompt (dispatch-layer wrapper) |
| `dispatch/loop_prompts/CODER.md` | Coder role prompt |
| `dispatch/loop_prompts/NONCODER.md` | Non-coder role prompt (requester + maintainer) |
| `audit/PROTOCOL.md` | builder ↔ Auditor contract — **wins on any verification conflict** |
| `audit/ARCHITECT_LOOP_PROMPT.md` | the architect's audit-layer loop |
| `audit/AUDITOR_LOOP_PROMPT.md` | the auditor's loop |
| `audit/watcher.sh` | audit-lane state deriver + watcher |

No code changes are needed in any of them. `dispatch.sh`, `watcher.sh` and `rotate_trail.py` take
their locations from their own script directory or from flags.

## Tier B — write once for the new project

| File | What to put in it |
|---|---|
| `dispatch/BINDINGS.md` | every `<TOKEN>` the portable files use, plus caps, hosting/launch commands, the hot-file registry, and the escalation precedents this project has actually paid for |
| `audit/<PROJECT>_BINDINGS.md` | the audit layer's term resolution + gap-fills. Name it after the project so a re-copy of `PROTOCOL.md` can never clobber it |
| `dispatch/roster/<instance-id>.md` | one per instance. Adding a file adds an instance — nothing hardcodes the roster |
| the project's own DoD bindings | the answers to `DEFINITION_OF_DONE.md`'s questions, plus any rows this project adds. Lives with the project's governance docs, not in this tree |
| `dispatch/board.md`, `dispatch/trail.md` | seed the headers only |

**Tokens BINDINGS must resolve before the first lane is dispatched.** An unbound token is a stand-up
error, not an empty cell:

`<ORCH_ROOT>` · `<DISPATCH_ROOT>` · `<AUDIT_ROOT>` · `<AUDIT_LANE_DIR>` · `<WORKTREE_DIR>` ·
`<TAG_PREFIX>` · the stakeholder · shared branch · change registers · the test command per surface ·
the contract check · the long-running test command · the content self-test · live-stack verification
· the device-only marker · caps and the stall window.

## Tier B′ — copy and adapt (project-coupled scripts)

These are useful shapes, not portable code. Each hardcodes a repo path, a package manager, or a test
target. Copy them as starting points and rewrite the project-specific lines; do **not** treat an
unedited copy as working.

| Script | What is coupled |
|---|---|
| `dispatch/dispatch_launch.sh` | absolute repo path, cost-tier table, worktree convention |
| `dispatch/dispatch_audit.sh` | test runner, suite runtime, corpus-test path, forbidden-file list |
| `dispatch/dispatch_verify.sh` | the ground-truth checks for this repo's layout |
| `dispatch/run_full_suite.sh` | the full-suite command and its output contract |
| `dispatch/intake/*.TEMPLATE.md` | the intake draft shape — but its category list, bug-source reference and exclusion rules are this project's |

## Tier C — never copy (runtime state)

`dispatch/lanes/` · `dispatch/intake/` (except the `*.TEMPLATE.md` above) · `dispatch/DELIVERY_PLAN.md` ·
`audit/cr/` · `audit/runs/` · `audit/regression/` · `audit/audit-trail.md` · `history/lanes/` ·
`history/trail/`

These are one repo's operational history. Copying them imports another project's lanes, verdicts and
regression pins as if they were yours — creating exactly the fabricated evidence the audit layer
exists to prevent. Create the directories empty. `DELIVERY_PLAN.md` is the Architect's *current* wave
plan — dated, greenlit by one stakeholder, scoped to specific work-item ids; a new project writes its
own when it has a wave to plan, and inheriting someone else's reads as a mandate nobody gave.

## Standing it up

1. Copy tier A. Copy tier B′ if you want the launch helpers.
2. Write the two BINDINGS files, resolving every token above.
3. Write one `roster/<instance-id>.md` per intended instance.
4. Point the project's governance checklist at `DEFINITION_OF_DONE.md` and answer its rows.
5. Seed `board.md` / `trail.md` headers; create the tier-C directories empty.
6. `sh dispatch/dispatch.sh state` — it should print an empty board without error. That is the
   replication smoke test.

## Keeping the split honest

The split rots in one direction only: a rule gets clearer when you cite the incident that produced
it, so project detail drifts *into* the portable files. Re-run the check when you touch this tree:

```sh
# from the orchestration root — every hit is a candidate defect in the split
grep -rniE "<this project's name>|<hosts>|<the stakeholder's name>" \
  README.md ROLES.md DEFINITION_OF_DONE.md history/README.md \
  audit/PROTOCOL.md audit/*_LOOP_PROMPT.md audit/watcher.sh \
  dispatch/DISPATCH_PROTOCOL.md dispatch/dispatch.sh dispatch/rotate_trail.py \
  dispatch/loop_prompts/
```

Write the incident down where it belongs: the rule in the portable file, the evidence in BINDINGS.
