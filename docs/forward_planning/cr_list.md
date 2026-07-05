# Change-request register — AMI Trade

The register of **planned change** — new work, not fixes. A CR is anything that adds or
changes behaviour versus the current build: a feature, a refactor, a process change, a
content or infra change. (Fixing something already broken is a **Defect** —
see [`../defect/def_list.md`](../defect/def_list.md).)

Governance rationale: decision **D-058** in [`../initial_specs/11_decisions/decision_log.md`](../initial_specs/11_decisions/decision_log.md).

## How a CR works

- **Auto-file, proceed.** Saiful's prompt IS the approval. When he asks for a change,
  Claude assigns the next `CR###`, creates its folder, files the CR doc, then implements —
  no separate approval gate.
- **ID:** `CR###`, zero-padded, sequential, never reused.
- **Folder:** every CR gets `docs/forward_planning/CR###_<snake_case_topic>/`. It holds at
  minimum `CR###_<topic>.md` (what / why / scope / acceptance). All design docs, notes, and
  sub-specs for that change live in its folder.
- **Commit tag:** the fix/feat commit carries `(AT:R<N> CR###)` after the summary, e.g.
  `feat(journal): search across entries (AT:R42 CR007)`.
- **Exempt from needing a CR:** process commits — handover wraps (`chore(handover)`),
  TestFlight/build version bumps, and docs-only commits. These keep the plain `(AT:R<N>)` tag.

**Status:** `proposed` · `in_progress` · `done` · `dropped`.

## Register

| CR | Date | Title | Status | Folder | Session |
|---|---|---|---|---|---|
| CR001 | 2026-07-05 | Change governance — CR/Defect registers + docs restructure | done | [CR001_change_governance/](CR001_change_governance/) | AT:R48 |
