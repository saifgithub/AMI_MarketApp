# RES008 — Testing the "AI trading edge" claims

**Goal:** take the AI-powered trading edges that are popular on YouTube, test each one as
taught, and turn every claim that fails into a video-ready report. The reports feed a YouTube
channel that promotes AMI Trade on fundamentals and sound method rather than on a promised edge.

**This is a test programme, not a hit list.** Each claim is tested to *prove or disprove*. A
claim that holds up is reported as holding up. RES001 ran ~50 pre-registered tests under the
same discipline and one of its four publishable findings was that a practitioner was *right*.

The folder is named as commissioned. The public framing is different — see "Publication rules".

---

## Layout

| Path | What it is |
|:--|:--|
| [`TRACKER.md`](TRACKER.md) | **The register.** Every claim ever looked at, its status and verdict. Check it before starting anything; a closed row is not revisited. |
| [`00_claim_landscape.md`](00_claim_landscape.md) | What is being claimed on YouTube, clustered, with measured reach. No channels named. |
| [`01_prior_work.md`](01_prior_work.md) | What RES001 and the earlier `saifgithub` repos already tested, so it is reused and not redone. |
| [`CHANNEL_PLAN.md`](CHANNEL_PLAN.md) | The channel: positioning, episode format, release order, how it points at the app. |
| [`FIVE_QUESTIONS.md`](FIVE_QUESTIONS.md) | The one-pager behind the series: five questions to ask of any trading claim, each with a measured example from a closed claim. |
| `C##_<slug>/` | One folder per claim — see below. |
| `_internal/` | **Git-ignored.** Source video IDs, channel names, transcripts index. Provenance for us; never published, never committed (this repo is public). |

### One claim = one folder

```
C##_<slug>/
  PREREGISTRATION.md   hypothesis, recipe as taught, data, metrics, kill criteria — committed BEFORE code runs
  code/                everything needed to reproduce; imports nothing from backend/app/
  out/                 raw outputs (json/csv) the results quote from
  RESULTS.md           what happened, with windows and intervals; deviations from the prereg stated
  VIDEO_BRIEF.md       for every verdict except HOLDS: hook, claim, test, reveal, why, how to check the next one
```

Tests are run **per claim, from this folder** — claim code imports `common`, and two claims share a
test-file name, so a bare folder-wide `pytest` fails at collection:

```bash
cd docs/Research/RES008_exposing_fraud
.venv/bin/python -m pytest common -q
.venv/bin/python -m pytest C05_99pct_scalping_recipe -q    # one claim at a time
```

Claim IDs are `C01…`, sequential, never reused — same rule as `RES###`.

---

## Method standard (inherited from RES001, tightened for public use)

1. **Pre-register before running.** `PREREGISTRATION.md` is git-committed before the test code
   executes. The commit hash goes in the tracker. If the spec changes after results are seen,
   `RESULTS.md` says so in its first section.
2. **Test the claim as taught, then test it fairly.** Arm A reproduces the recipe exactly as the
   videos present it (same indicator, same parameters, same kind of window) so nobody can say we
   tested a strawman. Arm B is the same recipe under honest conditions: out-of-sample window,
   transaction costs, many instruments rather than the one shown.
3. **Always a placebo or naive baseline.** Buy-and-hold, a persistence forecast, or a
   matched-random-entry control with the same trade count and holding period. A result that does
   not beat its placebo is not a result.
4. **Many instruments, fixed in advance.** The universe is listed in the pre-registration. No
   ticker is added or dropped after results are seen.
5. **Block bootstrap intervals, not p-values; no Sharpe.** Daily returns are autocorrelated and
   mean returns are poorly estimable at these sample sizes (Lo 2002). Report the window and the
   interval every time. No annualised figure from a short window.
6. **Costs are stated, conservative, and the same for every arm.**
7. **Nothing here touches production code** (Research README rule 2). Code runs on the Mac
   against `backend/.venv` or a throwaway research venv; it writes only inside its own folder.

### Verdict vocabulary

| Verdict | Meaning | Gets a debunk video? |
|:--|:--|:--|
| `DISPROVED` | Pre-registered kill criteria met; the claim fails as taught *and* under fair conditions | yes |
| `NOT SUPPORTED` | No evidence for it, but our test cannot rule it out (data resolution, sample) | yes, framed as "no evidence", never "false" |
| `PARTLY HOLDS` | A real effect exists but not the advertised one (size, cost, capacity, who can capture it) | yes, framed as "what is true and what is not" |
| `HOLDS` | Survived the fair arm | no debunk — report it honestly; candidate "what actually works" episode |
| `UNTESTABLE` | We lack the data or the claim is unfalsifiable as stated | optional "why you can't check this" episode |

---

## Publication rules

1. **Claims, never channels.** No creator, channel, video title, thumbnail, clip or link appears
   in any committed file or any published video. We describe the *class* of claim and its
   measured reach ("N videos, X combined views, measured on date"). Provenance stays in
   `_internal/`.
2. **"We tested this claim" — never "these people are lying."** Most of what fails here fails
   through ordinary error: overfitting, look-ahead, no costs, a persistence forecast mistaken for
   prediction. We cannot see intent and RES001 already ruled that we cannot call anyone a fraud.
   Public copy does not use *fraud*, *scam* or *liar* about any identifiable party.
3. **No edge is offered in return.** AMI Trade is a simulation-only training product and AMI is
   not licensed to give investment advice. Every episode ends on method — how to check a claim
   yourself, position sizing, costs, process — never on "here is what works instead".
4. **Brand voice:** analyst-to-analyst, numbers over adjectives, no puffery. The AI is called
   **AMI** anywhere a viewer might read or hear it.
5. **Reproducible.** Each episode can link the claim folder: pre-registration, code, outputs.
   That is the differentiator — the people we are answering show a screenshot.
