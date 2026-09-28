# CR247 — Evaluate a teammate's Room agent-prompt critique, to improve LLM reasoning quality

**Status: proposed, minted for deep evaluation — NOT a quick prompt swap.**
Filed by investigator session (AT:R85), 2026-09-28. A teammate reviewed the
Room's 12-agent/6-phase design and proposed both structural critiques and
rewritten system prompts for each agent, aimed explicitly at improving
LLM reasoning quality on mid-to-long-term fundamental evaluation. Saiful's
own framing for why this CR exists: *"the reason why we are doing the
evaluation... is to improve the quality of the LLM reasoning."* On minting:
*"indicate that a deeper analysis is needed as improvements at this level
requires higher effort."*

**This is a genuine evaluation, not an adoption or a rejection.** The
teammate's perspective is external and worth taking seriously — some of
it lands on real, unaddressed gaps; some of it re-proposes things already
decided with measured evidence; and the concrete prompt rewrite submitted
so far has at least one checkable defect. All three of those need to be
sorted out by someone doing the harder work this CR is scoped for, not
assumed from a first read.

## Why this needs real effort, not a quick swap

Saiful's own instruction: this needs a **higher-effort pass**, because
prompt changes at this level interact with a LOT of already-measured,
already-shipped machinery — CR197's causal ablation of the risk debate,
CR151's asymmetry-line disclaimer, DEF255's horizon-field distinction, the
lane-gating system (CR145/CR219), the fact sheet's actual data contract
(what's real vs. never-fetched) — and a prompt rewrite that looks better in
isolation can silently break or duplicate any of those. The assigned agent
should read the relevant prior CRs before rewriting anything, not just the
persona files.

## The critique, presented fairly

The teammate's review (quoted/paraphrased) made four points:

1. **Technical-Fundamental Horizon Mismatch** — pairing a Fundamentals
   Analyst with a Technical Strategist risks short-term technical noise
   (14-day RSI, moving averages) overriding a sound long-term fundamental
   thesis, since "raw technical data inside a multi-agent debate often
   misguides LLMs into short-term market timing."
2. **Social Sentiment Echo Chamber** — a Reddit-only sentiment aggregator
   risks skewing the Bull/Bear debate toward retail hype rather than
   intrinsic value; "long-term fundamental allocators care about
   institutional ownership, insider buying, and cash flow — not Reddit
   meme sentiment."
3. **Premature Execution and Sizing** — the Execution Desk proposes a
   concrete trade (side/size/entry/stop/target) BEFORE the Risk Officers
   weigh in; "LLM agents tend to anchor heavily on the first numerical
   proposal they see," so risk debate compute may get spent litigating
   minor sizing tweaks around a flawed entry rather than the entry itself.
4. **Deterministic Gatekeeping praise** — called the PM's non-skippable
   compliance check "the gold standard" for protecting the account from
   model hallucination.

Alongside the critique, the teammate submitted a full first-draft rewrite
of all 12 agents' system prompts. Saiful reviewed it and told the teammate
it was "rubbish" and to try again. The teammate's second attempt, submitted
so far only for the **Fundamentals Analyst**, is materially more rigorous
— structured as a numbered evaluation sequence, explicit `DATA DEFICIT:
[metric]` handling for missing fields, a demand for precise ratios over
vague language, and a 1.0–10.0 health score with a 3-bullet summary.

## What the investigating session already checked — starting point for the deeper pass

**Critique 1 (horizon mismatch) — partially already addressed, not fully
resolved.** `DEF255` (`backend/app/services/room_prompts.py:468-476`)
already distinguishes the trade's own **thesis horizon** (`horizon_days`)
from the mandate's **investment horizon** — exactly the two concepts the
teammate's critique risks conflating, so the app already has the
vocabulary this critique needs. What's NOT resolved: nothing in
`market_analyst.md` or `trader.md` currently instructs the Technical
Strategist or the Trader to explicitly WEIGHT a short-term technical
reading down when the mandate's horizon is long — the distinction exists
as a data field, not yet as a directional instruction. Worth the assigned
agent confirming precisely, then deciding whether a persona addition is
warranted.

**Critique 2 (social echo chamber) — the premise is wrong, but there may
still be a real point underneath it.** The Fundamentals Analyst **already
receives** institutional and insider ownership percentages today
(`content/agents/fundamentals_analyst.md:67-70`: *"Ownership — institutional
and insider percentages, shares outstanding and free float... a large
company with a small float, or one where insiders hold a third of the
shares, is a different instrument to size a position in"*) — the critique's
claim that this data doesn't exist anywhere in the system is factually
wrong. **CR244** (EDGAR company data + agent feeds, in progress) is
separately adding real insider TRANSACTION data (Form 3/4/5, not just
static ownership %) to Bull/Bear Researcher specifically. So the
underlying concern (should retail sentiment carry real weight in a
long-term fundamental debate) may still be worth asking, but not on the
premise that institutional/insider signal is currently absent — it isn't,
and CR244 is already expanding it further. The assigned agent should
re-frame this critique against what's real before deciding if there's a
genuine gap (e.g., "should Reddit sentiment influence LONG-term fundamental
mandates specifically, even though the signal exists elsewhere for a
different purpose").

**Critique 3 (premature execution / anchoring) — already tested, and the
naive anchoring story was explicitly ruled out by measurement.** CR197's
own causal ablation (`docs/forward_planning/CR197_risk_debate_effectiveness/REPORT.md:163-166`)
directly modeled and rejected simple anchoring as the mechanism at work:
*"Simple recency anchoring explains that without the debate... Anchoring
predicts approvals at or above baseline. Observed: 10.3%, the second-lowest"*
— i.e., CR197 measured what a pure anchoring effect would predict and
found the REAL data didn't match it. CR197's actual finding was the
opposite of "the Trader's number distorts the debate": stripping the risk
debate entirely roughly HALVES approvals, because the debate's function is
"option generation, not persuasion" — the PM needs the debate to hand it
alternatives to the Trader's one number, not protection from anchoring on
it. **This doesn't mean the critique is worthless** — CR197 tested
"debate vs. no debate," not "Trader-before-Risk-Officers vs.
Risk-Officers-before-Trader" specifically, so the exact reordering the
teammate proposes has never been tried. But the assigned agent should
know CR197 exists and read it in full before treating anchoring as an
open, unexamined risk — it's a measured, partially-addressed question,
not a blind spot.

**Critique 4 — accurately described, already shipped, no action needed.**
The deterministic PM compliance gate is real, already built, and already
non-skippable per CLAUDE.md's own safety-floor rule.

**The submitted Fundamentals Analyst v2 prompt has a concrete, checkable
defect: it asks for data the fact sheet does not supply.** Compared
directly against the real `content/agents/fundamentals_analyst.md`
(read in full):
- Asks for **ROIC** (Return on Invested Capital) — not a field anywhere in
  the real persona's input list.
- Asks to **"compare against 5-year historical medians and direct sector
  competitors"** — the real persona explicitly disclaims this TWICE:
  *"a category, not a numeric peer-average P/E (no peer-basket comparison
  is computed)"* and *"Still no peer-basket or sector-average comparison
  of any kind."*
- Asks whether growth is **"trapped in working capital"** — no working-capital
  line exists on the fact sheet per the real persona's input list.
- Asks to flag **"pension deficits"** and **"off-balance-sheet liabilities"**
  — neither is a fetched field anywhere in the real persona.

Shipping this prompt as written would force the LLM to either **hallucinate**
these figures — exactly the failure mode CLAUDE.md's degrade-loudly rule
(CR040) exists to prevent — or produce constant, spurious `DATA DEFICIT`
flags on fields that were never going to be available, which tests nothing
about prompt quality and would look like the app failing when it's the
prompt asking for data collection that doesn't exist. **This needs fixing
before any live comparison test, not noted and shipped anyway.**

## A methodology warning for the assigned agent

A background verification pass run for this CR's own drafting produced a
report **directly contradicting** two facts stated above (claiming
`DEF255`/`horizon_days` "does not exist anywhere in the repo" and that
`fundamentals_analyst.md` has no insider/institutional ownership field) —
both claims are wrong, reconfirmed by direct `grep`/file-read against the
real files immediately before this doc was finalized
(`room_prompts.py:468`, `fundamentals_analyst.md:67`). The contradicting
report even flagged its own tooling was unreliable mid-run. **Lesson for
whoever builds this CR: verify load-bearing facts yourself, directly,
before trusting a summary — including this doc's own claims.** This isn't
a one-off; it's exactly the kind of error this CR's whole premise depends
on avoiding (the Fundamentals Analyst v2 prompt's data-field mismatches
were caught the same way — reading the real file, not assuming).

## Scope for the assigned agent

1. **Read CR197, CR151 (asymmetry line), DEF255, and the lane-gating design
   rationale (CR145/CR219) before touching any persona file.** This CR
   exists because that reading is real work, not a formality.
2. **Fix or re-derive the Fundamentals Analyst v2 prompt** so every ask
   maps to a real fact-sheet field — either by dropping the unsupported
   asks (ROIC, peer comparison, pension/off-balance-sheet, working capital)
   or by first building the data pipeline to support them (a separate,
   much bigger CR if pursued — flag it, don't silently fold it in here).
3. **Evaluate critique 1 (horizon weighting) as a real, still-open
   question**: should `market_analyst`/`trader` explicitly downweight
   short-term technical signals when `mandate.horizon` is long? Design and
   test a persona change if warranted, using the app's own measurement
   discipline (a real before/after comparison on a real ticker set, not a
   vibes judgment).
4. **Re-scope critique 2** against the corrected premise (institutional/
   insider data already exists) — is there still a real, narrower question
   about retail-sentiment weighting for long-horizon mandates specifically?
5. **Evaluate critique 3 as a genuinely untested ordering question**:
   design a real ablation (Trader-before-Risk-Officers vs. reordered),
   in the spirit of CR197's own methodology, rather than assuming either
   the critique or the status quo is right without measurement.
6. **Evaluate and, where warranted, rewrite the remaining 11 agents'
   prompts** once the teammate (or Saiful) supplies revisions for them —
   only the Fundamentals Analyst has had a serious second draft so far;
   the other 11 are still at the teammate's rejected first-draft quality.
   Apply the same standard used above: every ask must map to a real data
   field, every structural change should be checked against existing
   measured findings before being treated as novel.
7. **Any change that ships must be measured**, following this codebase's
   own standing practice (CR197's ablation design, CR228's dial-run
   methodology) — a before/after comparison on a real ticker sample, not
   an assumed improvement.

## Non-goals

- Does not mandate adopting any specific rewritten prompt as-is — every
  rewrite needs the fact-sheet-field check and, where it changes behavior
  meaningfully, a real measurement before shipping.
- Does not relitigate CR197's core finding (option generation, not
  persuasion) without new evidence — the assigned agent tests the NARROWER
  ordering question (Trader-before-vs-after Risk Officers) CR197 didn't
  cover, not the whole debate-vs-no-debate question it already answered.
- Does not change the phase order, lane-gating architecture, or the
  deterministic PM gate without dedicated evidence — those are load-bearing,
  measured design decisions (CR145, CR197, CR219, the safety-floor rule),
  not to be casually reordered because a prompt review suggested it.
- Does not require building new data pipelines (ROIC, peer-comparison,
  pension data) as part of this CR — if the assigned agent concludes those
  are genuinely worth adding, that's its own, separate, larger CR.

## Acceptance (draft — refine at build time)

- Each of the 3 substantive critiques (horizon mismatch, sentiment
  weighting, execution ordering) has an explicit verdict: confirmed real
  and fixed, confirmed real and deferred (with reasoning), or found to be
  already addressed/not a real gap — never left unaddressed by omission.
- The Fundamentals Analyst prompt (and any other agent's, once revised)
  only asks for data the fact sheet can actually supply, or the CR
  explicitly flags a new data-pipeline need as future work.
- Any prompt change that ships is backed by a real before/after
  measurement on a real ticker sample, following the app's own established
  ablation methodology.
- The remaining 11 agents' prompts have been evaluated against the same
  standard, not left at the teammate's original draft quality by default.
