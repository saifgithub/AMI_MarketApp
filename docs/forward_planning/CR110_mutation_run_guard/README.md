# CR110 — make a mutation run structurally unable to lie

## Why

Mutation testing is how this project proves a guard is real: break the code on purpose,
watch the test go red, restore. On 2026-07-28 both halves of that loop produced
confident, meaningless results **inside a single session**:

| Lane | What the procedure did | Result |
|---|---|---|
| **DEF136** | ran the matrix with `pytest -x` | pytest stopped at the first failure; nobody saw that only one of two tests was firing. The responsiveness test was **green against a real regression** and was reported as proven. |
| **DEF127** | reverted mutations with `git checkout -- <file>` while the fix was uncommitted | git cannot tell a mutation from a fix. It deleted the fix mid-matrix; every number after the first was measured against partially-reverted code. |
| **DEF130** | the identical `git checkout` mistake | **~20 minutes after writing "never do this" into DEF127's hand-off.** |

The third row is the justification. The rule did not survive one hour as prose — which is
CLAUDE.md's own *"prompt instructions are not controls"* (CR038), turned on the
verification tooling. The discipline was living in a hand-off document, exactly where a
control must not live.

## Scope

- `scripts/mutation_guard.sh` — the control.
- `docs/initial_specs/08_tech/failure_patterns.md` — **P9**, all three instances.

Out of scope: retrofitting existing lanes. The script is for the next matrix, not a
re-run of past ones.

## Acceptance

The script must refuse, each with a distinct message, when:

1. the target file is **untracked** — git could not restore it at all (DEF127's `sse.py`
   kept its mutation because `git checkout` simply errored);
2. the target has **uncommitted changes** — the DEF127/DEF130 failure;
3. the test command contains **`-x` / `--exitfirst`** — the DEF136 failure;
4. the mutation **did not actually apply** — a green result there proves nothing.

It must always revert, then **verify the revert by reading `git status`** rather than
trusting the checkout. It must exit **3** — distinct from every other failure — when the
tests **pass** under the mutation, since that is the one outcome meaning the guard under
test is useless.

## Verified (2026-07-28, before commit)

| State | Exit | Want |
|---|---|---|
| happy path, mutation caught | 0 | 0 |
| test command contains `-x` | 1 | 1 |
| dirty target | 1 | 1 |
| untracked target | 1 | 1 |
| mutation did not apply | 1 | 1 |
| tests PASS under mutation | 3 | 3 |

Residual diff empty after every run.

## Known limitation — stated, not hidden

The script is **opt-in**. Nothing forces its use, so it lowers the cost of doing this
right rather than making the old way impossible. A hook refusing any `git checkout` of a
dirty file would be the stronger control; it is deliberately not built, because it would
fight legitimate use.
