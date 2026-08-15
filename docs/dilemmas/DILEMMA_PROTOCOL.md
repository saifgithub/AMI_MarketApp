# The Dilemma protocol — competing solutions to a hard, recurring problem

**Status:** standing procedure (CR185, 2026-08-15). **Owner:** Saiful decides; any agent may propose.

---

## What a Dilemma is, and what it is not

A **Dilemma** is a problem where the *right answer is genuinely unclear* and the cost of choosing
wrong is high enough to be worth several independent attempts.

It is **not** the default path for work. Almost everything is a CR or a Defect: the problem is
understood, the fix is known, one competent pass is correct and a second opinion buys nothing. Open a
Dilemma only when at least two of these hold:

- **We have already tried and failed.** Not "it is hard" — *we shipped a fix and it recurred*. The
  first attempt failing is a defect; the second is evidence the framing is wrong.
- **The obvious fix is the one that already failed.** If the instinctive answer is "do more of what
  we did", one agent will produce exactly that, confidently.
- **The choice is structural and expensive to reverse** — it touches shared infrastructure, sets a
  convention every future change must follow, or would have to be retrofitted across many sites.
- **The solution space is genuinely wide.** Static analysis vs runtime vs type system vs process are
  different *kinds* of answer, not variations on one.

If a problem is merely large, that is a CR with slices. If it is merely risky, that is a CR with
`GATE: independent`. A Dilemma is for when we do not trust our own framing.

---

## Why independent, blind attempts

The failure this protocol exists to prevent is **anchoring**. One agent's framing, read by the next,
becomes the shape of every subsequent answer — and if the framing is what was wrong, more effort
inside it produces more confident wrongness. Independence is the whole mechanism, so it is enforced
rather than requested:

- Every contributor writes **only** inside their own subfolder.
- Nobody reads another contributor's subfolder before submitting.
- The shared problem statement carries **symptoms, evidence and analysis of the problem** — never a
  proposed solution, not even the convening agent's. Analysis of *what is broken* is shared; ideas
  about *what to do* are not.

A contributor who has read another's answer can no longer provide an independent one. That is not a
rule about fairness — it is what makes the exercise worth its cost.

---

## Folder layout

```
docs/dilemmas/
  DILEMMA_PROTOCOL.md          ← this file
  ISS###_<SHORT_TOPIC>/
    ISS###_problem_statement.md   ← the shared brief. Symptoms + evidence + analysis. NO solutions.
    INVITE_PROMPT.md              ← the prompt Saiful pastes to invite a contributor
    ISS###_STATE.md               ← where the exercise stands. Kept current between sessions
    <model-name>/                 ← one folder per contributor, e.g. opus5.0/, gpt5/, kimi-k2/
      SOLUTION.md                 ← required: the proposal, in the shape the brief asks for
      <anything else>             ← prototypes, tests, benchmarks, diagrams — free rein
    VERDICT.md                    ← written last, after judging. Records what won and why
```

- **`ISS###_STATE.md` is the resume point**, and it exists because a Dilemma spans sessions by
  design: contributors arrive days apart, and the judging happens later still. It records who has
  submitted, what has been independently verified, what is frozen, and what decision is owed — so a
  cold session can be dropped back in without re-reading four proposals to work out where things
  stand. It is **not** a `HANDOVER_*` doc (CR097 retired those); it is per-issue state, and it lives
  with the issue rather than with a session.

- **IDs** are `ISS###`, zero-padded, sequential, never reused. The Architect mints them, same as
  `CR###` / `DEF###`.
- **Contributor folder names are the model's own name and version** (`opus5.0`, not `claude`), so a
  later reader can tell which capability produced which answer. If two runs of the same model are
  wanted, suffix them (`opus5.0-b`).

---

## Procedure

1. **Mint the ID and create the folder.** `docs/dilemmas/ISS###_<TOPIC>/`.
2. **Write the problem statement.** Symptoms, reproduction, full evidence, and the constraints a
   solution must satisfy. **Include every known location of the problem** — the winning solution has
   to be retrofitted to all of them, and the inventory is also how a reviewer checks whether a
   proposal actually covers the cases or only the interesting ones. State explicitly what is out of
   scope and what "done" means.
3. **Write the invite prompt.** Self-contained: a contributor should need nothing but this file and
   the repo. It must state the access rules, the constraints, the required output shape, and the
   no-peeking rule.
4. **The convening agent writes its own solution first**, in its own folder, before any other
   contributor is invited — so it cannot be influenced, and so the brief is proven usable by someone
   who was not the one who wrote it.
5. **Saiful invites others** by pasting the invite prompt. Contributors work blind and in parallel.
6. **Judging.** Saiful decides, or delegates to an agent that reads every folder. Either way the
   result is written to `VERDICT.md`: what won, what the runners-up contributed that the winner
   should absorb, and what was rejected and why. A losing idea that was *right about something* is
   recorded — that is half the value of having asked.
7. **Implementation is a normal CR**, laned and audited like anything else. The Dilemma produces a
   decision, not a shipped change. Reference `ISS###` in the CR.
8. **Close the loop.** If the problem was a recurring failure class, its entry in
   [`failure_patterns.md`](../initial_specs/08_tech/failure_patterns.md) gets the new guard, and its
   defect rows are updated to point at the CR that retrofitted them.

---

## Rules that make the result trustworthy

- **The brief must not contain a solution.** The convening agent will have opinions by the time it
  writes the brief; those go in its own folder. This is the rule most likely to be broken by
  accident, because a well-analysed problem statement drifts naturally toward its own answer.
- **No peeking, and say so in the invite.** Enforced by instruction, not by permissions — so it is
  stated plainly and a contributor who breaks it should say so rather than hide it.
- **Contributors write only in their own subfolder.** Default access is *read the whole repo, write
  one folder*. Anything more (running the suite, prototyping against real code) needs an isolated
  worktree and is granted per-Dilemma, not by default.
- **A proposal that cannot be checked is not a proposal.** Whatever is claimed — coverage, cost,
  performance — the submission must say how a reviewer verifies it. "This would catch all cases" is
  worthless without the means to test the claim.
- **Judge against the goal, not the states.** The question is never "which is most elegant" but
  "which one actually prevents the next instance, and how would we know?" — the same standard the
  audit protocol applies.

---

## When a Dilemma is the wrong tool

Say so and route it normally, rather than running the ceremony:

- The answer is known and the work is just large ⇒ **CR with slices**.
- The work is risky but the approach is agreed ⇒ **CR with `GATE: independent`**.
- Something is broken against spec ⇒ **Defect**.
- The decision is a product or business call ⇒ **ask Saiful**; competing agents cannot decide what
  the product should be.
