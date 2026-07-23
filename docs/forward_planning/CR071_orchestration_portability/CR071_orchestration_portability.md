# CR071 — Make `orchestration/` genuinely portable

**Status:** in progress · **Filed:** 2026-07-23 · **Track:** `AT:architect`
**Depends on:** [CR052](../CR052_orchestration_protocol/) (the protocol), [CR070](../CR070_orchestration_gate_reform/) (the gate reform)

## Why

Saiful, 2026-07-23:

> go through the orchestration files and
> 1. Remove any reference to my name
> 2. Ensure the files are "portable" ( not the binding or course )
> 3. Create the list of files that should be duplicated in each repo.

CR052 declared a portable-core / per-project-bindings split and CR070 deepened it (the Definition of
Done was given a portable half). Neither verified the split held. Measured before starting:

| Portable-candidate file | `Saiful` | project-specific terms\* |
|---|---|---|
| `audit/ARCHITECT_LOOP_PROMPT.md` | **5** | **27** |
| `audit/AUDITOR_LOOP_PROMPT.md` | 2 | 11 |
| `dispatch/loop_prompts/ARCHITECT.md` | 2 | 1 |
| `dispatch/loop_prompts/CODER.md` | 0 | 7 |
| `dispatch/DISPATCH_PROTOCOL.md` | 0 | 7 |
| `dispatch/loop_prompts/AUDITOR.md` | 0 | 4 |
| `dispatch/loop_prompts/NONCODER.md` | 0 | 3 |
| `dispatch/dispatch.sh` | 0 | 4 |
| `audit/PROTOCOL.md` | 0 | 1 |
| `ROLES.md`, `README.md`, `DEFINITION_OF_DONE.md`, `audit/watcher.sh` | 0 | ≤2 |

\* `grep -cEi "AMI Trade|AMI_MarketApp|melehost|agenticmarketintel|flutter|pytest|supabase|saifgithub|CLAUDE\.md|HANDOVER|docs/…|backend/|mobile/|CR0\d\d|DEF0\d\d"`

Two findings the counts alone don't show:

1. **`audit/PROTOCOL.md` was never this project's file to begin with.** It arrived as a verbatim copy
   from an upstream repo and still carried *that* repo's bindings inside what claimed to be the
   portable half: `src/`, `Forward_Planning/`, `DEF_LIST.MD`, a `GB10 3.11` deploy target, the branch
   `audit/frontier`, and `pytest audit/regression`. It also pointed at `audit/handshake/cr/`, a path
   that has not existed here since the tree moved under `orchestration/`. The bindings file's job was
   to translate all of it — which is backwards: the portable file should have held no bindings to
   translate. **A stale path in the contract document is the kind of thing that gets followed.**
2. **CR070 — my own work, one commit earlier — made this worse.** It added AMI Trade defect ids into
   portable prompts as evidence (`DEF084-MOBILE`, `DEF083`, `CR050`, `DEF059`, SHA `e344b27`).
   Citing the incident makes a rule more persuasive, which is exactly the pressure that rots the
   split. This is the drift direction the manifest now names explicitly.

## What changed

**Naming.** The protocol's term for the person is **"the stakeholder"** — already load-bearing in
`PROTOCOL.md` ("stakeholder-required guardrails", "stakeholder escalation"). `ROLES.md` now states
the equivalence normatively so "the human" and "the stakeholder" can't drift into two roles, and
adds: *who it resolves to is a BINDINGS entry, not a fact any portable file states.* The name appears
in exactly one place under `orchestration/` outside runtime state — the `The stakeholder` row in
`dispatch/BINDINGS.md`.

**Portable core (16 files) sanitized.** Zero name hits, zero project-term hits, zero work-item ids —
verified by grep after the edits. `audit/PROTOCOL.md` and `audit/ARCHITECT_LOOP_PROMPT.md` were
rewritten; `AUDITOR_LOOP_PROMPT.md`, `CODER.md` and `AUDITOR.md` substantially; the rest took
targeted edits. Command-bearing paths became tokens (`<ORCH_ROOT>`, `<DISPATCH_ROOT>`,
`<AUDIT_ROOT>`, `<AUDIT_LANE_DIR>`).

**Nothing was deleted, only relocated.** Every stripped fact landed in `dispatch/BINDINGS.md`:
concrete test commands (backend, mobile, contract check, long-running suite, content self-test), the
tokens above, and a new **Escalation precedents** table mapping each portable rule to the incident
here that produced it — DEF084-MOBILE, DEF083, DEF059, CR050, CR057, CR070. The rule stays portable;
the evidence stays local and traceable.

**`audit/AMI_TRADE_BINDINGS.md`** re-keyed: its left column named terms that no longer exist in
`PROTOCOL.md` (`audit/frontier`, `GB10 3.11`, `Rule 7`, `page_registry.json`). Four dead rows
dropped, six added.

**One stale binding fixed in passing:** `dispatch/BINDINGS.md` still described `auditor.core` as the
standing gate, which CR070 dropped. Now describes the three `GATE:` values.

**New: [`orchestration/PORTABLE_MANIFEST.md`](../../../orchestration/PORTABLE_MANIFEST.md)** —
deliverable 3. Four tiers: **A** copy verbatim (16 files) · **B** write once per project (BINDINGS ×2,
roster, DoD answers, seeded board/trail) · **B′** copy-and-adapt (the four project-coupled shell
scripts — each hardcodes a repo path, package manager or test target) · **C** never copy (`lanes/`,
`intake/`, `cr/`, `runs/`, `regression/`, `audit-trail.md`, `history/`). It lists every token BINDINGS
must resolve before the first dispatch, gives a replication smoke test, and carries the drift check.

## Scope

- `orchestration/**` documentation, prompts and script comments. **No executable logic changed** —
  `dispatch.sh`'s comment block was genericized, not its parsing.
- `orchestration/PORTABLE_MANIFEST.md` (new).

**Out of scope:** merging `dispatch/BINDINGS.md` with `audit/AMI_TRADE_BINDINGS.md` (D-1 implies it;
still owed). Runtime state and the two BINDINGS files keep their project content and the
stakeholder's name — that content is *correct* there, which is the whole point of the split.

## Acceptance

1. `grep -niE "saiful|AMI Trade|AMI_MarketApp|melehost|agenticmarketintel|saifgithub"` over the
   16 tier-A files returns nothing. ✅
2. Same for project terms (`flutter|pytest|uv run|CLAUDE.md|backend/|mobile/|docs/…|MABP|Aegis|GB10`)
   and for `CR0\d\d|DEF0\d\d`. ✅
3. Every fact removed from a portable file is present in a BINDINGS file. ✅
4. `sh orchestration/dispatch/dispatch.sh state` still derives the board correctly. ✅
5. `PORTABLE_MANIFEST.md` classifies every file under `orchestration/` into exactly one tier. ✅
6. Backend suite green (no source touched, but the tree is shared). ✅

## Residual risk

The split is convention-enforced, not tested. The drift check in the manifest is a `grep` a human or
agent has to remember to run — the same class of gap CR070 flagged in the stall rule. A CI check that
greps tier A for the project name would make it structural; not built, because this tree has no CI
hook and adding one for a docs check is not proportionate today. Named here rather than left implicit.
