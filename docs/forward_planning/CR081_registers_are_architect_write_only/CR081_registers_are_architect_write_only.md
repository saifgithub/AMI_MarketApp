# CR081 — The CR/Defect registers are generated, not hand-edited (was: Architect-write-only)

**Filed:** 2026-07-24 · **Track:** `AT:architect` · **Status:** done · **Model:** generated register
(evolved from the interim single-writer rule the same day — see *What (evolution)*).

## Why

On 2026-07-24, while laning DEF095 + DEF096, the Architect edited `docs/defect/def_list.md` to flip both
rows `open → laned`. Concurrently, track `AT:R59` added a `DEF098` row to the **same file** and committed
first. Because both tracks share one physical `main` checkout and `git commit` commits the whole index,
R59's commit (`945ed68`, tagged `AT:R59 DEF098`) **swept the Architect's two register edits into itself**.
The content survived — but the register's history now attributes the DEF095/096 laning to an unrelated
DEF098 commit.

This is a silent violation of the protocol's core invariant — **disjoint write-paths** (each writer owns
distinct files so concurrent commits never collide). The dispatch and audit handshakes already honour it
(one lane file per instance, one audit file per item). The **registers were the one shared table that
broke it**: `def_list.md` and `cr_list.md` are single monolithic markdown tables that multiple tracks
(requesters filing rows, the Architect flipping statuses) all write.

`git commit -- <paths>` with an explicit pathspec does **not** save you here: when two tracks edit the
*same* file, the second committer captures the union of both edits regardless of pathspec. The only real
fix is to remove the sharing — reduce the register to a single writer.

## What (evolution)

CR081 shipped in two steps on 2026-07-24:

**Step 1 — single-writer (interim, committed `d79a5e1`).** Non-architect tracks stopped editing the
registers; the Architect became the sole writer. This stops the race, but makes the Architect a
domain-agnostic chokepoint — including for a web-design CR that isn't the Architect's domain. Saiful:
*"what if a CR is a Webdesign change? That's not your domain."* That objection retired step 1 as the final
form.

**Step 2 — generated register (final; Saiful chose it 2026-07-24).** The registers are now **generated
artifacts**, the way `board.md` is derived from lane files:

- **Source of truth = one file per item:** `docs/defect/_registry/DEF###.row.md` /
  `docs/forward_planning/_registry/CR###.row.md`, each holding that item's single markdown table row. One
  file per item is a disjoint write-path, so concurrent commits never touch the same file — the sweep is
  **structurally impossible**, not merely policed.
- **The item's DOMAIN OWNER writes its row** (a web CR's row → `coder.web`, a backend DEF's → `coder.api`),
  not the Architect. "One owner" became "one owner *per item*" — which answers the web-design objection:
  the register is no longer an Architect chokepoint.
- **The Architect still mints the ID** (one integer minter → no ID-collision race). This answers Saiful's
  *"how would I tell you there's a CRxxx waiting? I'd have no number"*: you describe it, the Architect
  returns the number, the owner writes the row.
- **`scripts/registers/gen_registers.py gen`** rebuilds `def_list.md` / `cr_list.md` from the row files
  (sorted by ID). The `.md` tables carry a "GENERATED — do not hand-edit" banner. Migration was faithful:
  all **98 DEF + 79 CR** rows extracted verbatim (`verify` confirms content-identical, zero drift), the old
  blank-line-fragmented table collapsed to one clean table, the DEF backfill note preserved as a footer.

**Corollary — explicit-pathspec commits, never bare** (carried from step 1). On the shared checkout,
`git commit -m "…" -- <your files>`; never bare `git commit` / `git commit -am` / `git add -A` + commit.
Protects every disjoint-path file (row files included) from a cross-track sweep.

## Not changed

- **Requesters still file specs and pick their folder name.** The per-item spec folder was already disjoint.
- **Column shapes + status vocabulary** are unchanged — the generator reproduces the exact rows.
- **The `orchestration/dispatch/intake/` stub path** still exists for pre-triage items awaiting an ID.

## Acceptance

1. `def_list.md` / `cr_list.md` are generated from `_registry/*.row.md`, carry a GENERATED banner, and their
   "How to add" sections describe the mint-ID → owner-writes-row → regenerate flow. ✓
2. `scripts/registers/gen_registers.py` provides `extract` / `gen` / `verify`; `verify` confirms the live
   table's row-set + content equals the row files (no drift). ✓
3. Migration preserved every row: 98 DEF + 79 CR, content-identical to the pre-migration table. ✓
4. The rule names the 2026-07-24 incident so the *why* is not lost. ✓ (see Why)
5. `CLAUDE.md`'s change-governance section describes the generated model, not the retired single-writer one. ✓
6. This CR's own register row lives in `_registry/CR081.row.md` (dogfoods the model). ✓
