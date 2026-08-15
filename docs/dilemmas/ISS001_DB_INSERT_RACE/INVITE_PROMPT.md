# INVITE PROMPT — ISS001

**How to use this file:** paste everything below the line into a fresh session of the agent you want
to invite, running in the AMI Trade repo. Replace `<YOUR-MODEL-NAME>` with that model's name and
version (e.g. `gpt5`, `kimi-k2`, `gemini-3-pro`). Nothing else needs editing.

Invite each contributor in a **separate, fresh session**. Do not paste one contributor's answer into
another's session, and do not summarise one for another — that is the anchoring this exercise exists
to avoid.

---

You are contributing an independent solution to **ISS001**, a documented "Dilemma" in this
repository — a recurring problem where our own attempts have failed twice and we do not trust our
framing enough to just try again.

**Read these two files first, in full:**

1. `docs/dilemmas/ISS001_DB_INSERT_RACE/ISS001_problem_statement.md` — the problem, the complete
   evidence, the inventory of all 20 known occurrences, and what a solution must do.
2. `docs/dilemmas/DILEMMA_PROTOCOL.md` — how this process works and why it is run blind.

**The problem, in one line:** this backend writes "SELECT to check, then INSERT if absent" all over
the place; it is a race under two writers; we have named the pattern, automated a guard for it, and
filed two defects — and it kept getting written anyway, three more times in the week after the guard
went live. Your job is to work out what would actually stop the next one.

## The rules

- **Write ONLY inside `docs/dilemmas/ISS001_DB_INSERT_RACE/<YOUR-MODEL-NAME>/`.** Create that folder.
  Do not modify application code, tests, or any shared document. Do not commit anything outside your
  folder. Read as much of the repo as you like.
- **DO NOT read any other contributor's subfolder.** Sibling folders under
  `ISS001_DB_INSERT_RACE/` contain other models' answers — `opus5.0/` among them. Opening one
  destroys the independence that is the entire point of asking several of you, and a solution
  produced after reading another is worth less than no solution, because it looks independent and is
  not. **If you read one by accident, say so plainly at the top of your submission.** No penalty for
  admitting it; serious problem if you hide it.
- **The problem statement deliberately contains no proposed solution**, including from the agent that
  wrote it. That is not an oversight — do not go looking for "the intended answer". There isn't one
  yet.
- **You may propose changes to anything** in your write-up: the database layer, the session factory,
  the test guards, migrations, conventions, tooling. New third-party dependencies are allowed **if
  you justify them** — name the library, why it earns a place in a deliberately lean stack, and what
  it costs.
- **You cannot run the app.** This machine is an editor only — no backend, no database, no Docker.
  Backend unit tests do run (`cd backend && .venv/bin/python -m pytest tests/unit/ -q`, ~8.5 min,
  sqlite tempfile). If your proposal needs proving, write a self-contained demonstration **inside
  your own folder** rather than modifying the real suite.

## What to produce

A file `SOLUTION.md` in your folder. Cover, at minimum:

1. **What you propose**, concretely enough to implement — and state whether it **prevents**,
   **detects**, or **makes impossible** a new instance.
2. **How it handles per-site differences.** The last fix needed four *different* collision behaviours
   across seven sites (§3.5 of the brief). A design assuming one universal behaviour will not survive
   contact.
3. **How a reviewer verifies your claims.** If you assert coverage, cost, or performance, say how it
   is checked. An untestable claim will be treated as unsupported.
4. **What your solution would MISS.** This is not a formality. Every previous attempt here was
   confident and incomplete; a submission claiming total coverage without naming its own blind spot
   reads as not having looked for one.
5. **What it costs the next developer** writing an ordinary insert, and what happens when your
   control is wrong — loudly or silently?
6. **Retrofit plan** for the 11 open sites listed in the brief, including the four `User` inserts on
   the authentication path.

Anything else you want alongside it — prototype code, tests, a benchmark, a diagram, a comparison of
approaches you rejected — is welcome. Files may be named freely; only `SOLUTION.md` is required.

## How you will be judged

Not on elegance. On whether your solution plausibly stops the **21st instance**, and on whether a
reviewer can check that it does. A modest proposal with an honest account of its limits will beat an
ambitious one that claims to solve everything.

Be direct and terse. Numbers and tradeoffs, not sales language. If you think the problem is framed
wrongly, say so and explain why — that is a legitimate and useful submission.
