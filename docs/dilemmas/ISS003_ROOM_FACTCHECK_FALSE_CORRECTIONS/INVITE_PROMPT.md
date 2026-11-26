# INVITE PROMPT — ISS003

**How to use this file:** paste everything below the line into a fresh session of the agent you want
to invite, running in the AMI Trade repo. Replace `<YOUR-MODEL-NAME>` with that model's name and
version (e.g. `gpt5`, `kimi-k2`, `gemini-3-pro`). Nothing else needs editing.

Invite each contributor in a **separate, fresh session**. Do not paste one contributor's answer into
another's session, and do not summarise one for another — that is the anchoring this exercise exists
to avoid.

---

You are contributing an independent solution to **ISS003**, a documented "Dilemma" in this
repository — a recurring problem where our own attempts have failed twice and we do not trust our
framing enough to just try again.

**Work in this checkout, not the repo root.** ISS003 and the code it describes live on branch
`beta/cr267`, checked out at `/Volumes/Extreme Pro/AMI_MarketApp/.claude/worktrees/cr267-beta/`.
The repo root (`/Volumes/Extreme Pro/AMI_MarketApp/`) is on `main`, which has neither this brief nor
the three rounds of fact-check fixes. Every path below is relative to the worktree. If
`ISS003_problem_statement.md` is not where the next line says, stop and say so; do not answer
without it.

**Read these two files first, in full:**

1. `docs/dilemmas/ISS003_ROOM_FACTCHECK_FALSE_CORRECTIONS/ISS003_problem_statement.md` — the problem, the complete
   evidence from three rounds, and what a solution must address.
2. `docs/dilemmas/DILEMMA_PROTOCOL.md` — how this process works and why it is run blind.

**The problem, in one line:** each Room desk's prose is checked against the fact sheet by a deterministic matcher that, on a disagreement, tells the user in AMI's voice that the desk's figure is wrong; after two fixes it still "corrects" figures that are right, in new ways each round, while the protection it exists for (desks altering figures, CR038) is still needed. Your job is to work out what would actually solve it.

## The rules

- **Write ONLY inside `docs/dilemmas/ISS003_ROOM_FACTCHECK_FALSE_CORRECTIONS/<YOUR-MODEL-NAME>/`.** Create that folder.
  Do not modify application code, tests, or any shared document. Do not commit anything outside your
  folder. Read as much of the repo as you like.
- **DO NOT read any other contributor's subfolder.** Sibling folders under
  `ISS003_ROOM_FACTCHECK_FALSE_CORRECTIONS/` contain other models' answers. Opening one
  destroys the independence that is the entire point of asking several of you, and a solution
  produced after reading another is worth less than no solution, because it looks independent and is
  not. **If you read one by accident, say so plainly at the top of your submission.** No penalty for
  admitting it; serious problem if you hide it.
- **The problem statement deliberately contains no proposed solution**, including from the agent that
  wrote it. That is not an oversight — do not go looking for "the intended answer". There isn't one
  yet.
- **You may propose changes to anything** in your write-up: the fact-check itself, how desks write
  figures, the fact sheet, the Room pipeline, the UI, tests, conventions, tooling. New third-party dependencies are allowed **if
  you justify them** — name the library, why it earns a place in a deliberately lean stack, and what
  it costs.
- **You cannot run the app.** This machine is an editor only — no backend, no database, no Docker.
  Backend unit tests do run (`cd backend && .venv/bin/python -m pytest tests/unit/ -q`, ~30 min,
  sqlite tempfile; the fact-check tests alone: `tests/unit/test_def547*.py`, seconds). If your proposal needs proving, write a self-contained demonstration **inside
  your own folder** rather than modifying the real suite.

## What to produce

A file `SOLUTION.md` in your folder. Cover, at minimum:

1. **What you propose**, concretely enough to implement — and state whether it **prevents**,
   **detects**, or **makes impossible** a false correction reaching a user.
2. **The false-correction rate** you would accept for a user-visible note in AMI's voice, and how it
   is measured on a population of Rooms (US and Bursa), not on the one ticker in the brief.
3. **What happens to a fabricated or altered figure** under your proposal (the CR038 protection the
   check exists for). If you weaken it, say by how much and why that is acceptable.
4. **How it works when a market's sheet has fewer fields** (Bursa today), and for figures that are not
   sheet figures at all (a mandate cap, a multiple of a sheet figure, a figure from the debate).
5. **How a reviewer verifies your claims**, and how the next unseen phrasing is caught before users
   see it, plus how a regression is detected in production. An untestable claim is treated as
   unsupported.
6. **What your solution would MISS.** Every previous round here was confident and incomplete; a
   submission claiming total coverage without naming its own blind spot reads as not having looked.
7. **What it costs** (latency, model calls, developer effort per new sheet field), and what happens
   when your control is wrong: loudly or silently? House rules: degrade loudly (CR040), prompt
   instructions are not controls (CR038), users see the name AMI, on-prem models only on Alpha.

Anything else you want alongside it — prototype code, tests, a benchmark, a diagram, a comparison of
approaches you rejected — is welcome. Files may be named freely; only `SOLUTION.md` is required.

## How you will be judged

Not on elegance. On whether your solution plausibly stops **round 4** (the next unseen phrasing),
and on whether a reviewer can check that it does. A modest proposal with an honest account of its limits will beat an
ambitious one that claims to solve everything.

Be direct and terse. Numbers and tradeoffs, not sales language. If you think the problem is framed
wrongly, say so and explain why — that is a legitimate and useful submission.
