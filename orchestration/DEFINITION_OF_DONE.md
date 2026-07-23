<!--
DEFINITION_OF_DONE.md — PORTABLE CORE. Copy verbatim into any project adopting this orchestration
protocol; do not edit it per project. Every row here is a QUESTION plus what makes an answer valid.
The concrete commands, paths and formats that answer them live in the project's BINDINGS file, as
do any project-specific rows. Owner: CR070 (supersedes the AMI-Trade-only
docs/governance/CR_DEFINITION_OF_DONE.md, which is now a pointer).
-->

# Definition of Done — portable core

The evidence table an item carries when it is submitted for audit. An independent auditor checks
this table before calling anything COMPLETE.

## Scope: CR-level only

**The DoD is filled in once, for the whole work item — never per chunk.**

A CR may be delivered as *chunks + a CR-level audit*, or as *CR-only*. Either way the CR-level audit
is mandatory, and the DoD belongs to it. Chunks carry a shorter evidence list (see the CODER loop
prompt); they do not render this table.

This is not a formality. If chunks rendered the DoD, most rows would be honestly unanswerable at
chunk scope — a chunk cannot update a register row or a user manual — so every chunk submission
would arrive with a column of `N/A`s, the auditor would learn to wave `N/A`s through, and the rule
that *a false `N/A` is a MAJOR* would be dead by the time it reached the CR-level audit, where it is
the only thing standing between an unfinished item and `COMPLETE`.

## How to fill it in

Every row gets a **disposition**: evidence, or `N/A` with a one-line reason. A submission with a
missing table, an empty row, or a bare `N/A` is **incomplete** and bounces.

Valid evidence is something a reader can re-run or re-read:

- a command **and** its observed output — not "tests pass"
- a `file:line` reference — not "updated the docs"
- an observed result from exercising the real thing — not "should work"

A claim that could have been written without doing the work is not evidence.

## Section A — Verification (is it correct?)

| Row | The question it asks | What makes a disposition valid |
|---|---|---|
| **Scope** | Does the change match the item spec's stated scope and acceptance? | Names the spec, and states what was in and out |
| **Tests** | Is the project's test gate green over the changed code? | The command run and its observed result |
| **Manual verification** | Was the real behaviour exercised, not assumed? | How it was exercised and what was observed |
| **Scope discipline** | Is anything unrelated bundled into this change? | Confirmed against the actual diff, not from memory |
| **Contract integrity** | Do the seams this change crosses still hold? | Re-verified against the real counterpart, not just compilation |

## Section B — Deliverables (is it finished?)

| Row | The question it asks | What makes a disposition valid |
|---|---|---|
| **Docs** | Is behaviour that changed reflected where it is documented? | The file(s) updated, or why none needed it |
| **Commit tag** | Is authorship and the item id traceable from history? | The tag as it appears on the commit(s) |
| **Register** | Does the item's register row reflect its real status? | The row as it now reads |
| **Model / effort / budget** | Which tier did this run at, under what cap, and why? | Tier, cap, and a one-line justification. Start cheap; an expensive run needs a reason |

Findings in Section A mean **it is broken**. Findings in Section B mean **it is unfinished**. They
carry different severities and usually different owners — a missing user manual is not a failing
build, and routing both as one undifferentiated "MAJOR" teaches everyone to discount the label.

## Rules for projects adopting this

1. **Core rows may be dispositioned but never removed.** A project with no test suite writes
   `N/A — no test suite exists`. That is visible and slightly embarrassing, which is the point: a
   removable row guarantees nothing, and a DoD that can be edited down to what a project already
   does is decoration.
2. **Projects add rows; they never subtract them.** Additions go in the BINDINGS file — a user
   manual, a video guide, a changelog entry, a migration runbook, whatever this project owes before
   an item is finished. Put them in the section they belong to.
3. **This core ships no commands.** Not one path, not one test invocation. A project that inherits
   another project's `curl` line cannot run it, dispositions the row `N/A`, and has manufactured
   exactly the false `N/A` the auditor is told to treat as a MAJOR.
4. **An unbound row is a stand-up error, not an empty cell.** Every core row must have an answer in
   BINDINGS before the first item is dispatched — including `N/A` with its reason. Discovering a row
   has no binding *during* an audit is too late; the audit is already blocked on it.
5. **The auditor spot-checks dispositions independently.** A filled-in table is a claim. A missing
   table or a false `N/A` is a MAJOR.

## Why this is split

The rows are universal; the answers never are. "Tests" means something in every project and the same
thing in none of them. Keeping the questions portable and the answers local is what lets the protocol
be copied into a new project without either rewriting the checklist or inheriting a checklist that
describes somebody else's repo.
