# 08 — Personas (addendum)

Added 2026-08-12 after Saiful's review: *"I am surprised that you went into this without
first considering the personas of the people using this app."* Correct — `01`–`06` measured
surfaces and cited general UX law, and the A+E recommendation silently assumed a
novice-majority audience. This file makes the assumption explicit, tests it against the
specs and against real alpha behaviour, and re-runs the recommendation through it.

Two honest findings up front: **the specs contain no persona document** (the closest are
the tier narratives in `06_monetization/tiers_and_pricing.md` and the audience sketch in
`00_overview/vision_and_positioning.md`), and **the alpha data almost is one** — 172 real
users leave usage trails that segment cleanly.

## 8.1 What the alpha data says (melehost, 2026-08-12, real-human filter)

Filter: the standing exclusion list (CR035 synthetics, seed fixtures, CR125/DEF227-229
probes — `memory/feedback_user_report_exclusions.md`). Counts include Saiful's own
test-device reinstalls; genuine externals are somewhat fewer. 84 of the 172 arrived in the
last 14 days (the TestFlight/Play wave), so recent installs dilute lifetime rates —
directions below are robust, exact percentages are not.

| Behaviour | Users | % of 172 |
|---|---|---|
| Any core action at all (room / 1-on-1 / lesson / trade / challenge) | 47 | 27% |
| **No core action whatsoever** | **125** | **73%** |
| Did lessons | 30 | 17% |
| Convened the Room ever | 32 | 19% |
| Convened 3+ times | 9 | 5% |
| Placed a sim trade | 8 | 5% |
| Opened any 1-on-1 chat | 11 | 6% |
| — of which with a *trading* agent (not Concierge) | 5 | 3% |
| Messaged the Concierge | 9 | 5% |
| **Brief Your Agent edits** | **0** | **0%** |
| Persisted a mandate | 28 | 16% |

Caveat on the mandate row: DEF060 (mandate discarded during onboarding) was **fixed at
AT:R59**, so the lifetime count mixes pre-fix users whose completed interviews left no
mandate with post-fix users measured cleanly. The clean read is the recent cohort: of the
**84 users created in the last 14 days (all post-fix), 18 persisted a mandate (21%) and 7
convened (8%)**. Four of five fresh installs abandon the ~3-minute interview before the
Floor is ever seen.

Three readings that matter for this research:

1. **The modal real user is a door-bouncer.** 73% install and do nothing measurable. The
   complaint ("walking into a meeting…") is the testimony of people at exactly this stage;
   the data can't prove the Floor causes the bounce, but the largest cohort by far is the
   one the shipped Floor serves worst.
2. **The depth features the Floor advertises are used by almost nobody yet.** 13 identity
   marks at rest advertise 1-on-1 and briefing; 6% ever opened a 1-on-1, 3% reached a
   trading agent, 0% briefed. The at-rest roster is a lobby for rooms ~no one enters.
3. **The users who DO act, convene.** 32 convene vs 8 trade vs 4 challenge. The Room is the
   observed centre of gravity — consistent with the north-star metric (WAU with ≥1
   convene), and with putting CONVENE on screen one.

## 8.2 The four personas

Synthesised from: the vision doc's audience ("knows *about* trading, has no scaffolding for
*deciding*"), the tier ladder, the v1.0 market commitments (AR/MS, halal-first), and the
behavioural segments above. Names are working labels for this lane.

### P1 — The Curious Beginner (largest today; Floor Pass)
Downloaded from a store listing about "learning to invest with an AI team." Knows a P/E
from a podcast. No existing relationship to any of the twelve job titles — *Bull Researcher
vs Aggressive Debator* is noise on day one. Wants: one clear thing to do, quick wins,
permission to not understand everything yet. Data shadow: the 73% no-action cohort + the
17% lessons-first users.
**Floor today:** thirteen strangers and a locked org chart. **Risk:** bounces silently
(CR043 — no feedback path), which is indistinguishable from what the data shows.

### P2 — The Verdict Seeker (the observed active core; Floor Pass → Trader)
Has tickers, wants a structured second opinion and the *why*. Values the debate as
credibility for the verdict, not as entertainment. Watches the live Room the first couple
of times, then wants the answer. Data shadow: 19% convened, 5% repeat, 5% traded.
**Floor today:** the CTA that defines them sits 1.63 folds down. **This persona is the
north-star metric.**

### P3 — The Team Manager (aspirational; Trader → Floor Manager)
The user the shipped Floor was designed for: knows their agents by name, opens 1-on-1s,
would tune an agent's brief, watches the floor work. The moat personas — Brief Your Agent
and the Decision Journal — are built for them. Data shadow today: **≤6%, briefs 0%.** They
are real (the tier ladder needs them) but they are *made, not acquired* — nobody installs
as a P3; P2s grow into P3 after trust forms.
**Floor today:** correct for them — and they are the one persona progressive disclosure
cannot hurt, because depth-seeking is the defining trait.

### P4 — The Halal-first Learner (v1.0 commitment; AR/MS)
Sharia screening as first-class mandate flag, Arabic/Malay UI, possibly RTL. Everything P1
is, plus: twelve English finance job titles at once is a *translation* problem as much as a
cognitive one (CR160 already fights this fight), and trust routes through the mandate
("it knows my rules") more than through org-chart theatre. Not yet in the alpha data;
locked as a market by the decision log.
**Floor today:** P1's problem, amplified by language and jargon density.

## 8.3 Concepts re-run through the personas

✓ serves · △ neutral/mitigated · ✗ harms

| | P1 Beginner | P2 Verdict Seeker | P3 Team Manager | P4 Halal-first |
|---|---|---|---|---|
| Baseline Floor | ✗ 13 strangers first | ✗ CTA below roster | ✓ built for them | ✗ jargon wall |
| A Concierge home | ✓ one face, one ask | ✓ CONVENE on screen 1 | △ one tap deeper; seat-count row + A2 bands arguably *better* for management | ✓ one voice to translate; mandate-aware status line |
| B Briefing home | △ needs positions to brief | ✓ | △ | △ digest translation cost ×3 languages |
| C Task home | ✓ | ✓ | ✗ firm invisible | ✓ |
| D Collapsed floor | △ roster still the greeting | △ CTA 0.83 folds | ✓ | △ |
| E Narrative room | ✓ 4 stages, not 12 seats | ✓ verdict-first journey | △ WATCH THE FLOOR persisted — their view survives | ✓ 4 desk labels to parse, not 12 titles |
| F Depth dial | ✗ wrong default finds them | △ | △ | ✗ doubles translation surface |

## 8.4 Does the recommendation survive the persona pass?

**Yes — and it sharpens.** A+E is the only pairing that serves P1/P2/P4 (today's ~94% and
the v1.0 growth market) without cutting off the P2→P3 growth path:

- The persona the shipped Floor optimises for (P3) is measured at ≤6% with its flagship
  feature at 0% usage. Designing the *landing surface* for them is inverted priority; they
  are exactly the users who will find the firm row, the desk bands and WATCH THE FLOOR,
  because depth-seeking defines them.
- P3 is *made from* P2 — and A+E improves the making: A2's desk bands with seat counts and
  earn paths are a better "run your firm" surface than the flat Wrap, and E2's desk
  drill-down teaches the org chart *while it works*, in context, instead of as a lobby
  poster.
- The strongest persona argument for A specifically: P4. One Concierge voice + four desk
  labels localises; thirteen simultaneous identities in Arabic/Malay does not.

**What the persona pass changes:**

1. **Priority correction (new):** the data says the biggest funnel loss is *before* the
   Floor — post-DEF060-fix, only 21% of fresh installs finish the interview (18/84, last 14
   days). A home redesign polishes the second door while four of five users leave at the
   first. Any home CR should ship **with interview-abandonment instrumentation** (which
   question loses people is currently unmeasured) — added to `05`'s sequencing as step 0.
   The interview itself is locked conversational (D-018); the fix is knowing where it
   leaks, then shortening the leak, not replacing it with a form.
2. **P3 mitigation becomes acceptance criteria, not garnish:** the firm-row seat count and
   the persisted WATCH THE FLOOR toggle are the load-bearing D-003 mitigations; a build
   that drops either has changed the recommendation.
3. **Persona telemetry:** whichever CR ships should tag the four segments (bounce /
   convene / depth / locale) so the next research round starts from cohorts, not from a
   relayed quote. Cheap: the events already exist in the tables queried here.

## 8.5 Limits

Behavioural segments are not interviewed humans: n=172 includes founder devices, 84
accounts are <14 days old, and inactivity can mean "abandoned the interview" (the measured
majority path), "bounced off the Floor," or "installed and got busy." The four personas are
evidence-weighted hypotheses. The cheapest upgrade: 5 short calls with real testers — P1/P2
split confirms or kills this file. Queries are reproducible; SQL shape recorded in
`sources.md`.
