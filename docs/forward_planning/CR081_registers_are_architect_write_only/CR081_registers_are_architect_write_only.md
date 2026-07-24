# CR081 — The CR/Defect registers are Architect-write-only

**Filed:** 2026-07-24 · **Track:** `AT:architect` · **Status:** done

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

## What

**One writer per register: the Architect.** Encoded as a behaviour-critical rule in
[`CLAUDE.md`](../../../CLAUDE.md) (loaded into every track's session, so every non-architect reads it):

- Non-architect tracks **never edit** `def_list.md` or `cr_list.md`.
- They file their `DEF###_<topic>/` / `CR###_<topic>/` **spec folder** — a disjoint path they own alone —
  and drop a one-line stub in `orchestration/dispatch/intake/`.
- The **Architect** assigns the canonical ID, writes the register row, and owns every status flip
  (`open → laned → fixed`). This also removes the ID-collision race (two requesters can no longer both
  claim the next number in the table).

**Corollary — explicit-pathspec commits, never bare.** On the shared checkout, commit with
`git commit -m "…" -- <your files>`; never bare `git commit` / `git commit -am` / `git add -A` + commit,
which stage-and-sweep whatever another track left dirty. This protects every *disjoint-path* file from the
cross-track sweep (the register fix above handles the one *shared* file).

## Not changed

- **Requesters still file specs and pick their folder name.** The single-writer rule constrains only the
  shared register *table*, not the per-item spec folder (which is already disjoint). The Architect
  reconciles the ID when transcribing the row, so a folder-name collision is caught at mint time.
- **The registers stay hand-maintained markdown for now.** The fuller fix — per-defect status in spec
  frontmatter + a regenerated `def_list.md` (the way `board.md` is regenerated from lane files), so the
  table is never hand-edited at all — is deferred. Single-writer is sufficient to stop the race; filed as
  a follow-up option if register contention recurs.

## Acceptance

1. `CLAUDE.md` states, in the Change-governance section, that `def_list.md` and `cr_list.md` are
   Architect-write-only, with the intake-stub path for non-architects and the explicit-pathspec commit
   corollary.
2. The rule names the 2026-07-24 incident so the *why* is not lost.
3. This CR's own register row is written by the Architect (dogfoods the rule).
