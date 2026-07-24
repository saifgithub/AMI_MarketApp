# Change-request register — AMI Trade

<!-- GENERATED FILE — do not hand-edit. Source of truth: docs/forward_planning/_registry/<CR###>.row.md
     (one file per CR). Rebuild: python scripts/registers/gen_registers.py gen cr. CR081. -->
> **Generated — do not hand-edit this table.** Each row's source is
> `_registry/<CR###>.row.md` (one file per CR); rebuild with
> `scripts/registers/gen_registers.py gen cr`. See [How a CR works](#how-a-cr-works).

The register of **planned change** — new work, not fixes. A CR is anything that adds or
changes behaviour versus the current build: a feature, a refactor, a process change, a
content or infra change. (Fixing something already broken is a **Defect** —
see [`../defect/def_list.md`](../defect/def_list.md).)

Governance rationale: decision **D-058** in [`../initial_specs/11_decisions/decision_log.md`](../initial_specs/11_decisions/decision_log.md).

## How a CR works

- **This table is generated — never hand-edit it.** Each row's source is
  `_registry/CR###.row.md` (one file per CR = a disjoint write-path); rebuild with
  `python scripts/registers/gen_registers.py gen cr`. A shared monolithic table gets *swept*
  on the shared `main` checkout ([CR081](CR081_registers_are_architect_write_only/CR081_registers_are_architect_write_only.md));
  one-file-per-item removes the shared write entirely.
- **Auto-file, proceed.** Saiful's prompt IS the approval. When he asks for a change, the
  **Architect mints the next `CR###`** (one minter, no ID-collision race); its **domain
  owner** writes `_registry/CR###.row.md` + creates the folder + files the CR doc, then
  implements — no separate approval gate. A web CR's row is written by `coder.web`, a backend
  CR's by `coder.api`, etc. — the register is no longer an Architect chokepoint (it only mints
  the number, which is domain-agnostic).
- **ID:** `CR###`, zero-padded, sequential, never reused.
- **Folder:** every CR gets `docs/forward_planning/CR###_<snake_case_topic>/`. It holds at
  minimum `CR###_<topic>.md` (what / why / scope / acceptance). All design docs, notes, and
  sub-specs for that change live in its folder.
- **Regenerate + pathspec-commit:** after writing/editing a row file, run the generator and
  `git commit -m "…" -- <your row file> docs/forward_planning/cr_list.md`. Never bare /
  `-am` / `git add -A`.
- **Commit tag:** the fix/feat commit carries `(AT:R<N> CR###)` after the summary, e.g.
  `feat(journal): search across entries (AT:R42 CR007)`.
- **Exempt from needing a CR:** process commits — handover wraps (`chore(handover)`),
  TestFlight/build version bumps, and docs-only commits. These keep the plain `(AT:R<N>)` tag.

**Status:** `proposed` · `in_progress` · `done` · `dropped`.

## Register

| CR | Date | Title | Status | Folder | Session |
|---|---|---|---|---|---|
