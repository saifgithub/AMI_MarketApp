# ISS002 — invitation to contribute

You are being asked to solve a hard, recurring problem in the AMI Trade repository, independently
and blind. Several contributors are answering the same brief in parallel; the value of the exercise
comes entirely from your not being anchored by anyone else's framing.

## Access rules

- Read anything in the repository.
- **Write only inside your own folder:** `docs/dilemmas/ISS002_WIRE_CONTRACT_UNPROVEN/<your-model-name>/`
- **Do not read any other contributor's folder** under `ISS002_WIRE_CONTRACT_UNPROVEN/` before you
  submit. A contributor who has read another's answer can no longer provide an independent one.
- Do not modify production code. Prototypes go in your folder.
- Mac is a pure editor — no backend, no database, no Docker. Backend unit tests run with
  `backend/.venv/bin/python -m pytest backend/tests/unit/ -q` (sqlite tempfile fixture).

## The brief

Read `docs/dilemmas/ISS002_WIRE_CONTRACT_UNPROVEN/ISS002_problem_statement.md` in full. It carries
the symptoms, three worked instances with evidence, an inventory of six shapes any solution must
handle, the constraints, and the definition of done. **It deliberately contains no proposed
solution — not even the convening agent's.** If you find yourself looking for the intended answer,
there isn't one.

Also read `docs/dilemmas/DILEMMA_PROTOCOL.md` for why this is run blind.

## What to produce

`SOLUTION.md` in your own folder, in the shape the brief's final section specifies — your reading of
the problem, the mechanism, item-by-item coverage of the six-item inventory, costs, failure modes,
and what would make your answer the wrong choice. Prototypes, tests and measurements alongside it
count for a great deal.

**If you think the brief's framing is wrong, say so.** That is the most valuable contribution
available here — this exercise exists because the framing is the suspect, not the effort.
