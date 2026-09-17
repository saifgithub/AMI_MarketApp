# RES008 — Channel plan

How the research becomes a YouTube channel that sells AMI Trade on method instead of on a promised
edge. Campaign-brief structure; every target below is a **proposal** — no baseline exists yet, so
none of these numbers is a forecast.

---

## 1. Overview

**Working series name:** *Pre-Registered.* (alternatives: *We Tested It* · *The Holdout*). The name
is the method, which is the differentiator.

**One sentence:** We take the AI trading edges with millions of views, write down in public what
would convince us, run the test, and show the result — with the code.

**Primary objective (proposed):** installs of the free tier (Floor Pass) attributable to the
channel. First 90 days after launch: 12 long-form episodes published, and a measured
view → description-click → install funnel in place. Volume targets get set after the first four
episodes give a baseline; setting them before that would be inventing numbers.

**Secondary:** (a) brand trust ahead of release — AMI is the app that shows its working;
(b) a public, citable body of tests (the repo) that outlives any single video;
(c) a supply of verified lesson material for the BOK (each closed claim is a sourced lesson).

## 2. Audience

**Primary — "about to try it".** Retail traders, 20–45, who watch AI-trading content and are one
video away from buying an indicator, renting a bot, or pasting a chatbot strategy into a live
account. They are not stupid and not anti-technology; they have never been shown what a fair test
looks like. They search: *does X work*, *X strategy tested*, *X bot review*, *is X legit*.

**Secondary — "builds things".** The Python / data-science audience behind the multi-million-view
ML-prediction tutorials. They will read the repo. They are the ones who link us in a comment
thread when someone posts an overlay chart.

**Tertiary — sceptical-finance viewers** who already watch the explainers that take hype apart.
Small, high-trust, high share-rate.

Where they are: YouTube search and suggested; r/algotrading, r/Daytrading, r/learnmachinelearning
(strict self-promotion rules — contribute results, not links); X fin/quant circles; TradingView
script comments. Stage: problem-aware, solution-confused.

## 3. Messages

**Core:** *Don't take our word for it either. Here is the test, here is the code, here is what
happened.*

| Supporting message | Proof point |
|:--|:--|
| The claim lives in the title; the evidence is a screenshot. | Landscape survey: 38 videos read, none of the strategy-tester results included costs or a holdout; in 16 the video body undercuts its own title. |
| A fair test has five parts anyone can ask for: written down first · out-of-sample · costs · a placebo · enough trades. | Every episode applies the same five. The pre-registration commit is on screen. |
| What is real in markets is mostly **risk**, not **prediction**. | P20/P21: volatility is forecastable and sizing on it homogenises risk — and it *costs* return. Reported as plainly as the nulls. |
| We sell no edge. AMI Trade is a simulator: practise the process with a twelve-analyst team and no real money. | Simulation-only, by design and by licence. Said in every episode. |

**Tone by surface.** Long-form: analyst-to-analyst, unhurried, numbers first. Shorts: one chart,
one sentence, no sneer. Reddit/X: the result and the repo link, nothing promotional. Never
mocking — the viewer we want is the one who believed the claim last week.

**Hierarchy inside an episode:** why you should care (you are about to risk money on this) → what
we did → what happened → how to check the next one yourself → where to practise (AMI, ten seconds).

## 4. Channels

| Channel | Why | Format | Effort |
|:--|:--|:--|:--|
| **YouTube long-form** (primary) | Where the claims live and where "X tested" is searched | 8–12 min, faceless: charts, screen-recorded pre-registration, voice-over. One claim per episode | High |
| **YouTube Shorts** | Discovery; the reveal chart is a natural 30-second unit | One per episode: claim → chart → one line | Low |
| **Episode page on the AMI site** | Search ("does LSTM stock prediction work"), a home for the numbers, the install link | Summary, the key chart, link to the claim folder, disclaimer | Low–medium |
| **GitHub claim folders** (already public) | The credibility asset; what lets a stranger verify us | README per claim, pre-registration, code, outputs | Already produced by the research |
| **Reddit / X** | Earned reach among builders and sceptics | Post the finding as a contribution; link the repo, not the app | Low, careful |
| **In-app** | Closes the loop: each closed claim becomes a lesson | BOK lesson per claim (CR060 sourcing applies; EN edit flags AR/MS re-translation) | Medium, later |

No paid media at launch. Revisit once there is a measured click-to-install rate to buy against.

## 5. Episode format (every episode, same spine)

| Beat | Time | Content |
|:--|:--|:--|
| Cold open | 0:00–0:20 | The claim in the words a viewer has heard, and its measured reach ("videos making this claim have N million views"). No channel, no clip, no thumbnail of anyone's. |
| The stakes | 0:20–0:50 | What a viewer does next if they believe it, and what that costs. |
| What would convince us | 0:50–2:00 | The pre-registration on screen: hypothesis, what would support the claim, the commit hash and date. "We wrote this before we ran anything." |
| The test, as taught | 2:00–4:00 | Reproduce the recipe exactly. Show that we *can* get their picture. |
| The fair test | 4:00–7:00 | Holdout, costs, many instruments, placebo. The reveal chart. |
| Why | 7:00–9:00 | The mechanism of the failure in one idea (persistence, selection, geometry, inventory, luck). |
| What is true | 9:00–10:00 | The honest remainder — what part of the claim, if any, survived. |
| Check the next one yourself | 10:00–11:00 | One question to ask of any similar video. |
| AMI | last 15 s | Simulation-only; practise process, not predictions. Link. Disclaimer card. |

**Standing rules** (from the README's publication rules): claims not channels · "we tested", never
"they lied" · no edge offered · AMI by name · not investment advice · reproducible.

**Titles must be true.** The genre's trick is a title the video does not support; ours carry the
result. Pattern: *"We tested the [claim]. [Number]."* — e.g. "We tested the 99% win-rate
strategy. It won 4 times in 10."

## 6. Release order and calendar

Episodes are ordered by verdict strength × reach, and a claim that holds changes the line-up.
All eight C-claims closed on 2026-09-17; §6a is the resulting order.

### 6a. Release order (verdicts as of 2026-09-17)

**Ordering rule.** `DISPROVED` first, largest measured reach first. Then `NOT SUPPORTED`. The one
`PARTLY HOLDS` runs after the episode it depends on. Three judgment calls override the sort, each
stated: C04 leads because it explains the win-rate number that headlines most claim classes; C03 follows C02 because it is the same
viewer's next step; C01 runs ahead of C08 (smaller reach) because it opens the builders' audience
(§2) on an evergreen search term. Reach is views of the videos we read, not a forecast of ours.

| Wk | Episode | Verdict | Reach of the claim class | Why here | Depends on |
|:--|:--|:--|:--|:--|:--|
| 1 | **C04** — a 90% win rate proves it works | `DISPROVED` | 4 videos · 2.99M | The explainer for the number the other episodes keep meeting. Its brief uses C05, C06 and C07 as worked examples; C02's brief links back to it. Evergreen keyword. | — |
| 2 | **C07** — "I gave an AI bot real money" | `DISPROVED` | 2 videos · 6.12M | Largest reach in the survey. | — |
| 3 | **C02** — a chatbot wrote me a profitable strategy | `DISPROVED` | 3 videos · 3.28M | Second-largest reach. | links C04 |
| 4 | **C03** — keep tweaking until the backtest is spectacular | `DISPROVED` | inside C02's videos + 2 | The sequel to week 3: what the viewer does after the chatbot's first draft. **Review point** (§8) after this one. | C02 out |
| 5 | **C01** — a neural network predicts tomorrow's price | `NOT SUPPORTED` | 2 videos · 1.95M | Opens the builders' audience; strongest single visual in the series. First episode where one of our predictions missed — say so. | — |
| 6 | **C08** — a chatbot's ten stock picks beat the index | `NOT SUPPORTED` | 2 videos · 2.76M | Pairs with C07 on "how long luck lasts". | links C07 |
| 7 | **P20 + P21** — what *is* real: volatility is forecastable, and it costs return | `HOLDS` | — (ours) | Mid-series proof that we publish what holds. Supports message 3 (§3). | [brief](P_prior_work/P20_P21_what_is_real/VIDEO_BRIEF.md) · RES001 names practitioners — see the brief's flag |
| 8 | **C05** — the "99% win rate" recipe | `PARTLY HOLDS` | 2 videos · 2.17M | The "what is true and what is not" episode: headline fails (33–44%), a secondary condition scored for the claim under a yardstick we then found flawed. Needs C04's dial first. | C04 out · **Saiful: publish as is, or hold for the B09 re-test** |
| 9 | **P06** — a contest-winning return proves skill | `NOT SUPPORTED` | — (prior work) | Same idea as C07/C08 from another angle; brief exists. | — |
| 10 | **C06** — an "AI" grid robot earns passive income | `NOT SUPPORTED` | 3 videos · 0.92M | Smallest reach; two of our four predictions were wrong, which the episode leads with. | — |
| 11 | **P01** — machine learning predicts stock direction | `DISPROVED` | — (prior work) | Follow-up for the C01 audience; brief exists. | C01 out |
| 12 | **P04** — stop after k losses | `DISPROVED` mechanically | — (prior work) | Closes on behaviour, the bridge to what AMI Trade trains. | — |

**Cadence.** Weekly is the ceiling (§9); at one a fortnight the order is unchanged and the table
spans 24 weeks. Each episode's Short goes out 2–3 days after it; the Reddit/X post (result + repo
link, never the app) goes with C03, C01 and P01, where the builders are.

**Before week 1.** Channel identity, description and pinned-comment templates, store campaign
links (§8 cannot measure installs without them), lawyer read (§9) — and three episodes finished
and banked, so a slipped week does not break the run.

**What changes this table.** (a) If C05 is held, P02 + P03 ("volatility signals that do not
predict direction") take week 8 and C05 returns after B09. (b) A verified error in any closed
claim pulls its episode until the correction is in the repo. (c) After the week-4 review, title
pattern and runtime may change; the order does not.

## 7. Assets to produce

| Asset | What | Priority |
|:--|:--|:--|
| Chart pack per episode | The figures in each claim's `out/`, restyled in the AMI hex palette, 16:9, dark | must |
| Script per episode | From each `VIDEO_BRIEF.md` | must |
| Channel identity | Name, banner, avatar, 3-second sting — AMI hex language | must, before episode 1 |
| Description template | Summary, repo link, install link (UTM), disclaimer, "no channel is named, by policy" | must |
| Pinned-comment template | Pre-registration commit + how to reproduce | must |
| Episode page template (site) | One per claim | should |
| "How to read a trading claim" one-pager | The five questions; lead magnet and in-app lesson | should |
| Shorts cut-downs | One per episode | should |

## 8. Measurement

| Metric | Source | Note |
|:--|:--|:--|
| **Installs attributed to the channel** (primary) | UTM on description and site links → store listing campaign parameters | Needs the store campaign links set up before episode 1 |
| Click-through from description | YouTube Analytics | The funnel step we control |
| Average view duration; retention at the reveal beat | YouTube Analytics | Tells us whether the format holds |
| Impressions CTR by title pattern | YouTube Analytics | Tests whether truthful titles can compete |
| Search vs suggested share | YouTube Analytics | Are we being found by "X tested"? |
| Repo traffic / stars | GitHub | The builders' audience |

Review after episode 4, then monthly. No targets until then.

## 9. Risks

| Risk | Mitigation |
|:--|:--|
| A creator recognises their claim and responds, or a viewer reads an episode as an accusation | Claims-not-channels rule; no clips, titles or thumbnails; "we tested this claim" language; landscape finding that many creators *already* show the refutation is stated generously. A lawyer's read of the disclaimer and the fair-comment posture before launch (Saiful). |
| "You're selling an app too" | Say it first, in every episode: what AMI is, that it is simulation-only, that it promises no edge. |
| Drifting into investment advice | Episodes end on method, never on a recommendation. Standard disclaimer card. AMI is not licensed to advise — restated in the README rules. |
| A claim holds up | Publish it as holding. It is the best credibility asset the channel can have. |
| Truthful titles under-perform bait | Measure it (CTR by title pattern) rather than assume. The reveal-number pattern is itself a curiosity hook. |
| Production load on a two-person team | Faceless format; charts come straight from `out/`; one episode a week is the ceiling, one a fortnight is fine. |
| Our own error | Pre-registration, public code, a standing corrections policy: a verified error gets a pinned correction and a tracker entry. |

## 10. Next steps

**Saiful:** choose the series name; decide voice (own voice or synthetic); open the channel under
the AMI brand account; lawyer read of the disclaimer + posture; store campaign links for install
attribution.

**Saiful, from §6a:** publish C05 (`PARTLY HOLDS`) as written in week 8, or hold it for the B09
re-test; C02's title 1 uses the genre's search keyword (a vendor's chatbot name) — accept, or use
titles 2/3.

**Claude — done 2026-09-17:** eight claims closed; a `VIDEO_BRIEF.md` for all eight and for P01,
P04, P06; the five-questions one-pager ([`FIVE_QUESTIONS.md`](FIVE_QUESTIONS.md)).
**Claude — next:** P20 + P21 brief (week 7); chart packs in the AMI palette; scripts from the
briefs; episode-page template on the site; B09 pre-registration if C05 is held.
