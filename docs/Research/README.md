# Research — AMI Trade

Side investigations into trading methods, frameworks and claims. **Separate from the
CR/Defect pipeline on purpose.**

## What belongs here

Open questions about *whether something is true* — a published framework, a claimed edge,
a market mechanism. Work whose output is a finding, not a shipped change.

A CR is "we are going to build X." A RES is "we do not yet know whether X is real."
When a RES concludes and implies a build, it *spawns* a CR and links to it. It does not
become one.

## Rules

1. **Numbering:** `RES###`, zero-padded, sequential, never reused. One folder per item:
   `docs/Research/RES###_<topic>/`.
2. **Nothing here touches production code.** No imports from `backend/app/` into research
   code, no edits to live modules from a research finding. A finding that implies a change
   is written up here and filed as a CR to be built elsewhere.
3. **All code lives under the RES folder** — `RES###_<topic>/code/`. Outputs to `out/`.
4. **Pre-register before you run.** Anything with a measured result commits a
   `PREREGISTRATION.md` — hypothesis, method, thresholds, kill criteria — *before* the
   code runs, so git timestamps the design ahead of the outcome. Results go in a separate
   `RESULTS.md`. If the spec changes after seeing results, say so in the writeup; a
   silently retuned threshold is the failure mode this rule exists to prevent.
5. **No extrapolated numbers.** Report the window and the interval. A short-window
   annualised figure is not a result.

## Index

| ID | Topic | Status |
|:---|:---|:---|
| [RES001](RES001_finrl_x_review/) | FinRL-X (AI4Finance) — is it a usable basis for anything? | done |
| [RES002](RES002_orderflow_gamma_videos/) | Orderflow + gamma-exposure practitioner claims (2 videos) | done |
| [RES003](RES003_volatility_regime_sizing/) | Does volatility regime modulate risk but not direction? | done — mechanism real, trophy is not evidence |

## Pre-existing folders

`Alternatives/`, `benchmark/`, `UI/` predate this numbering and are left as they are.
New work gets a `RES###`.
