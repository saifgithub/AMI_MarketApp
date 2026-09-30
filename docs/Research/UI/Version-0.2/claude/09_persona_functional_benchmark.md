# 09 — Persona functional-needs benchmark

Companion to `08_personas.md` (2026-08-12) — not a redefinition. Where `08` establishes *who*
each persona is from real alpha telemetry, this file asks a narrower question per persona:
**what does this class of user functionally need, based on how comparable products serve that
segment, and does AMI Trade's actual feature set (built or planned) cover it?** Source for "what
AMI has": `docs/initial_specs/01_product/core_loop_and_features.md`'s feature inventory, cited by
release gate (🟢 Alpha / 🟡 v1.0 / 🔵 v1.1 / ⚪ Phase 2). No new persona, no marketing framing —
that shape was rejected for this pass (see `08_personas.md` for the persona-in-market context).

## 9.1 P1 — The Curious User

**Functional pattern.** Products that convert true novices — Duolingo-style habit-formation
apps, Robinhood Learn, beginner brokerage onboarding flows — share a narrow recipe: one obvious
next action per screen, jargon introduced one term at a time (not a glossary dump), a small win
inside the first session, and a failure state that doesn't end the session (wrong quiz answer →
remedial micro-lesson, not a dead end). The thing they avoid is presenting the *full system*
before the user has done anything — an org chart, a settings panel, a menu of twelve unfamiliar
roles reads as "I am not ready for this yet" and the user leaves rather than explores.

| Need | AMI feature | Release gate | Verdict |
|---|---|---|---|
| One obvious first action | Concierge conversational interview (Express path, 6 Q + 3 risk scenarios) | 🟢 Alpha | Covered — but see abandonment data below |
| Small early win | Trading Fundamentals lessons + AI-generated quizzes | 🟢 Alpha | Covered |
| Forgiving failure state | Remedial micro-lessons on quiz fail | 🟢 Alpha | Covered |
| Gradual reveal of the 12-agent system, not all at once | Agent Academy (12 modules, unlocks agents progressively) | 🟢 Alpha | Covered in spec |
| Landing screen that doesn't require system fluency | Honeycomb home (static at Alpha; animated 🟡 v1.0), 5-tab nav, Convene FAB | 🟢 Alpha | **Gap, per `08_personas.md` §8.4 finding 1** — the shipped Floor greets with the roster, not a single first task; this is exactly the mismatch the persona pass already flagged |

**Verdict.** The spec-level features that should serve P1 (progressive Agent Academy unlock,
remedial lessons) are built. The actual landing experience contradicts them — `08_personas.md`
already measured this as the largest gap (73% no-action, only 21% of fresh post-fix installs
persist a mandate). This isn't a new finding; it's the same gap, now traced to a specific
functional-pattern mismatch: novice-onboarding products front-load one task, AMI's shipped Floor
front-loads the org chart.

## 9.2 P2 — The Verdict Seeker

**Functional pattern.** Products built around "give me a structured answer" — sell-side research
notes, screener/signal tools, robo-advisor recommendation engines — succeed on three things:
speed to the answer, a visible reasoning trail that earns credibility (not a black-box score),
and an immediate path to act once the answer lands. Ceremony between "I asked" and "I got the
answer" is tolerated only if it visibly adds credibility (e.g. showing sources); ceremony that
reads as decoration is a drop-off point.

| Need | AMI feature | Release gate | Verdict |
|---|---|---|---|
| Fast time-to-verdict | Convene the Room (streaming logs + verdict) | 🟢 Alpha | Covered, mechanism exists |
| Visible reasoning as credibility, not entertainment | 12-agent debate, multi-round for Floor Manager | 🟢 Alpha (1 round); 🟡 v1.0 (multi-round, paid) | Covered |
| Immediate path to act on the verdict | Trade ticket with PM compliance pre-check | 🟢 Alpha | Covered |
| A record of *why*, for trust over time | Decision Journal (transcripts, search, replay) | 🟢 Alpha | Covered |
| Low ceremony between ask and answer | Convene CTA placement | — | **Gap, per `08_personas.md` §8.4** — CTA sits 1.63 folds down; the persona this feature is *for* has to scroll past the ceremony to reach it |

**Verdict.** Every backend capability this persona needs is built — the gap is entirely in
surfacing, already identified in `08_personas.md` as the north-star-persona's defining problem.
Nothing new to add functionally; the fix is presentation order, not new capability.

## 9.3 P3 — The Team Manager

**Functional pattern.** Power users of professional tools — Bloomberg Terminal customization,
TradingView Pro alerting/scripting, portfolio platforms with named/tunable strategies — expect
deep configurability, an audit trail of every change, the ability to override defaults, and
close to zero hand-holding. Products serving this segment succeed by getting out of the way once
competence is established; they fail by gating configurability behind onboarding flows built for
novices.

| Need | AMI feature | Release gate | Verdict |
|---|---|---|---|
| Tune the system's behavior directly | Brief Your Agent (conversational + Raw Mode editor) | 🟢 Alpha (conversational); 🟡 v1.0 (Raw Mode) | Covered in spec |
| Audit trail of changes | Coach version history (20 versions paid; unlimited + diff viewer, Floor Manager) | 🟢 Alpha / 🟡 v1.0 | Covered in spec |
| Deep multi-agent configurability | Multi-round debate (Floor Manager) | 🟡 v1.0 | Planned, not yet at Alpha |
| Per-agent accountability over time | Per-agent performance scorecards; mute/promote/weight agents | ⚪ Phase 2 | **Not built** — genuinely missing, not just unsurfaced |
| A management surface (not a lobby) | Firm/seat-count row, persisted "watch the floor" | — | Design-level mitigation identified in `08_personas.md` §8.4, not yet a shipped feature independent of the home redesign |

**Verdict.** The flagship feature built specifically for this persona (Brief Your Agent) is
shipped at Alpha with **0% usage** (`08_personas.md` §8.1) — this is not a discovery gap like P1
or a surfacing gap like P2, it's the "made, not acquired" reality: nobody arrives as a P3, they
grow into one after P2 trust forms, so a P3-first landing surface is solving for a population
that doesn't exist yet on install. The one genuine functional gap (not just an unmet-yet
timeline) is per-agent accountability — scorecards and mute/weight controls are Phase 2, and a
serious "team manager" persona will eventually want to know which of the 12 agents is actually
worth listening to, which the roster alone doesn't answer.

## 9.4 P4 — The Learner (AR/MS, halal-first)

**Functional pattern.** Faith-based and localized finance products (halal-screening apps,
zakat-calculation tools) that earn trust do it through **transparent screening methodology** —
users want to see *how* a security is being filtered (debt-ratio thresholds, excluded sectors),
not just a binary "halal" badge — plus market-appropriate language that simplifies jargon rather
than transliterating it, and trust signals specific to the market (which the vision doc already
identifies: halal/Sharia positioning is a stated moat, not a bolt-on).

| Need | AMI feature | Release gate | Verdict |
|---|---|---|---|
| Transparent screening methodology, not just a flag | Halal/Sharia mandate flag: universe filter + debt-ratio check + interest-bearing exclusion | 🟢 Alpha | Covered in spec |
| Additional common compliance filters | ESG-lite, no tobacco/alcohol/gambling, long-only, custom ticker block/allowlist | 🟢 Alpha | Covered in spec |
| Local-language delivery, not literal translation | Arabic (ar-SA) + Malay (ms-MY) + RTL support | 🟡 v1.0 | Planned, not yet at Alpha |
| The screening actually being enforced, not just displayed | Portfolio Manager compliance pre-check on every trade | 🟢 Alpha (mechanism) | **Gap — DEF061 (open):** 4 of 8 compliance toggles (`esg_lite`, `no_tobacco_alcohol_gambling`, `no_fossil_fuels`, `custom_constraints`) are presented as hard filters but the deterministic safety-floor check never reads them — only LLM prompt narration references them, and prompt instructions are not controls (CLAUDE.md's own house rule — ~70% ignore rate per CR038) |

**Verdict.** This is the persona where the gap is most severe relative to what's promised. The
positioning explicitly sells halal/Sharia screening as *the* moat for AR/MS markets, and the
methodology-transparency pattern this class of user needs is architecturally present (universe
filter + debt-ratio + exclusion logic exists). But DEF061 means half the compliance flags a P4
user would set are cosmetic — enforced only by LLM narration, not the deterministic check. For a
persona whose defining trust question is "does it actually follow my rules," an unenforced
toggle is worse than an absent one: it's a promise the product doesn't keep. This is not a new
finding — DEF061 is already open and CR036 already flags it as relevant to AR/MS launch
positioning — but this pass connects it specifically to P4's functional-needs pattern rather
than treating it as a generic backend defect.

## 9.5 Cross-persona summary

| Persona | Core functional need | Covered? | Gap type |
|---|---|---|---|
| P1 Curious User | One obvious first action, gradual system reveal | Spec: yes. Surfaced: no | Presentation/sequencing gap (largest funnel loss, already measured) |
| P2 Verdict Seeker | Fast, credible verdict → immediate action | Spec: yes. Surfaced: no | Presentation gap (CTA fold-depth) |
| P3 Team Manager | Deep configurability + per-agent accountability | Spec: mostly yes | Two gaps: (a) built feature at 0% usage — population doesn't exist yet, not a product defect; (b) per-agent scorecards genuinely unbuilt (Phase 2) |
| P4 Learner | Transparent, *enforced* faith-based screening | Spec: yes. Enforcement: no | Real functional gap — DEF061, open |

**Pattern across all four:** none of P1/P2/P4's gaps are missing capability — the backend
mechanisms exist. Three of four gaps are **the system not doing at runtime what its own spec and
UI promise** (unsurfaced-but-built for P1/P2, unenforced-but-displayed for P4). Only P3 has a
genuinely unbuilt piece (scorecards), and even that one is secondary to the more basic finding
that its flagship shipped feature has no users yet. This says the functional foundation is
largely sound; the highest-leverage work is sequencing/surfacing and closing DEF061, not new
feature development.
