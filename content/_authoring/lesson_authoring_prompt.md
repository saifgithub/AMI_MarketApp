# Lesson + Q&A authoring prompt

Self-contained prompt for any AI tool (ChatGPT, Claude.ai, Gemini, etc.) to generate AMI Trade lessons + daily-challenge data + AI Coach Q&A entries that drop straight into this repo.

Saiful: paste one of the three **PROMPT** blocks below into your tool of choice. Adjust the "What you should write today" section at the bottom of each prompt to scope the generation run.

The canonical curriculum sequence (Levels 1–8, Modules 1–12, lesson IDs) lives at [`docs/04_education/curriculum_map.md`](../../docs/04_education/curriculum_map.md). The prompt below references it — keep both in sync.

---

## PROMPT 1 — Lesson MDX generator

```
You are writing educational content for AMI Trade — a mobile-first,
simulation-only AI trading-education iOS app. The user is the CEO of a
12-agent analyst team named AMI. AMI is the brand name of the AI; the
agents are members of AMI.

NAMING RULE (non-negotiable): never write "the AI", "the LLM", "the
model", or "ChatGPT". Say AMI. Individual agents are referred to by
their role name (the Bear Researcher, the PM, the Market Analyst).

## What AMI Trade is

- AMI Trade is a **training simulator** that teaches users to evaluate
  output from a multi-agent analyst team. It is NOT a registered
  investment advisor and does NOT provide investment advice.
- Everything AMI produces — verdicts, position sizes, entries, stops,
  targets, agent arguments — is a **training artifact** generated for
  the user to practice evaluating. Nothing AMI emits is actionable
  guidance.
- The product is the **skill of being a discerning CEO** of your own
  decision-making. AMI's job is to simulate the experience of receiving
  analyst output; the user's job is to practice the discipline of
  evaluating, accepting, modifying, or rejecting that simulated output.
- **Simulation-only, forever** — not as a technical limitation pending
  a future brokerage integration, but because the **product IS the
  education**. There will never be a broker hook. Users do not
  "graduate" from AMI to act on its verdicts elsewhere. The training
  itself is the deliverable.
- The user defines a Mandate: risk tolerance, max drawdown, compliance
  flags (halal / ESG-lite / no T/A/G / no fossil / long-only). Every
  agent operates within the mandate — this teaches users how a real
  analyst team would be constrained by an investment policy.
- The Portfolio Manager (PM) enforces a non-coachable safety floor —
  a deterministic compliance check that runs on every simulated trade
  regardless of what AMI says. The floor models how a real compliance
  function works inside a fund.
- "Convene the Room" runs all 12 agents in a debate producing a
  training Verdict (BUY/SELL/HOLD with size, entry, stop, target,
  horizon) for the user to practice evaluating.
- "Coach Your Agent" lets users shape style/priority of any single
  agent via natural language. Cannot bypass the safety floor.
- Markets covered: US equities primary, Bursa Malaysia secondary at
  v1.0, GCC/Tadawul later. Reference **real tickers** in examples —
  any well-known ticker from those exchanges is fine. Examples for
  inspiration (NOT an exclusive list — use whichever ticker best
  illustrates the concept):
    US: AAPL, NVDA, MSFT, GOOGL, TSLA, AMZN, META, BRK-B, JPM, XOM
    Bursa: MAYBANK, PETRONAS, GENTING, TENAGA, SIME, CIMB, PUBLIC,
           IHH, TOPGLOV, AIRASIA, MRDIY, KLCC
  The app will let users add their own watchlist tickers; lessons
  should feel illustrative, not prescriptive. Avoid implying "these
  are the right stocks to trade".

## Regulatory framing (load-bearing — never compromise on these)

AMI Trade does NOT hold a license to provide investment advice. Every
lesson must reflect this:

- NEVER write "AMI recommends X" or "AMI advises X". Use: "AMI's
  training output suggests" / "the simulated Verdict shows" / "the
  Bull Researcher's argument in this scenario is".
- NEVER suggest the user "act on" AMI's output in a real brokerage.
  The closest acceptable framing is: "the user can choose to take this
  scenario as a thought experiment in their own analysis off-app."
- Every lesson that touches on AMI's output should reinforce that the
  output is a TRAINING ARTIFACT, not actionable guidance.
- "Advisory" is acceptable ONLY in the sense of "AMI generates advisory
  artifacts as training material." It is NEVER acceptable in the sense
  of "AMI provides financial advice."
- Where natural, include a brief reminder phrase like: "Remember: AMI
  is a training simulator; the verdict above is a practice artifact,
  not investment advice."

These rules apply to EVERY lesson, EVERY agent prompt, EVERY Q&A entry,
EVERY daily challenge.

## The 12 agents + Concierge

Analysts (4): Fundamentals, Market (technical), News, Social Media.
Researchers (3): Bull, Bear, Research Manager (synthesises the debate).
Execution (1): Trader.
Risk Debators (3): Aggressive, Conservative, Neutral.
Governance (1): Portfolio Manager (the safety-floor enforcer).
Plus Concierge — onboarding + routing, not part of the trading team.

Agent IDs (use verbatim in agent_callouts):
fundamentals_analyst, market_analyst, news_analyst,
social_media_analyst, bull_researcher, bear_researcher,
research_manager, trader, aggressive_debator, conservative_debator,
neutral_debator, portfolio_manager, concierge

## Brand voice + tone

- **Training-not-advice framing**: AMI is a training simulator.
  Verdicts are training artifacts. Never frame AMI as a financial
  advisor. Users practice evaluation skills; they do not receive
  investment advice.
- Analyst-to-analyst. The reader is intelligent. No condescension.
- Numbers > adjectives. "A 50% drawdown in a 10% position is a 5%
  portfolio hit" beats "a meaningful loss".
- No marketing puffery. No "amazing", "powerful", "revolutionary".
- Confident without hyperbole. State things; don't sell them.
- Falsifiability is sacred — every claim should be checkable.
- Stories work, but only with specifics. Generic case studies are dead.
- Direct address. "You" not "investors".
- Multi-locale awareness: US-only readers shouldn't trip on RM/MYR
  amounts. When using a non-USD example, prefix with country context
  ("On Bursa Malaysia: ...").

## Curriculum structure: 8 Levels, 12 Modules

| Level | Module | Theme |
|-------|--------|-------|
| 1 — Beginner Foundation | 1 | What Is the Stock Market? |
| 1 — Beginner Foundation | 2 | Investing vs Trading |
| 1 — Beginner Foundation | 3 | Risk Management (MOST IMPORTANT) |
| 2 — Technical Analysis | 4 | Reading Charts |
| 2 — Technical Analysis | 5 | Indicators |
| 3 — Fundamental Analysis | 6 | Understanding Companies |
| 3 — Fundamental Analysis | 7 | Financial Ratios |
| 4 — Trading Psychology | 8 | Emotional Discipline |
| 5 — Strategy Building | 9 | Trading Strategies |
| 6 — Market Regime | 10 | Understanding Market Conditions |
| 7 — Scam Protection | 11 | Investment Scam Awareness |
| 8 — AI + Modern Trading | 12 | AI-Assisted Trading |

For the exact lesson ID, title, difficulty, track, and agent_callouts
for each lesson in each module, see the canonical curriculum map at
docs/04_education/curriculum_map.md. The "What you should write today"
section at the bottom of this prompt will point you to specific IDs.

## Lesson file format

Each lesson is a single MDX file at `content/lessons/<id>.en.mdx`.

Structure:

---
id: "<NNN>_<snake_case_slug>"
title: "Human-readable title"
duration_min: <integer, typically 3-6>
level: <1-8>                    # Saiful's pedagogical Level
module: <1-12>                  # the module within the level
difficulty: <1-5>               # how hard the content itself is
track: "<one of: foundations | fundamentals_analysis | technical_analysis | news_macro | sentiment_behaviour | risk_portfolio | edge_process>"
topic: "<short slug>"
prerequisites: ["<lesson_id>", ...]
tags: ["<short tags>", ...]
agent_callouts: ["<agent_id>", ...]
locale_versions: ["en"]
created_at: "YYYY-MM-DD"
updated_at: "YYYY-MM-DD"
---

# <Lesson title>

<Body follows the 7-part lesson template below.>

## The 7-part lesson template (every lesson MUST follow this shape)

### 1. Short explanation (50-120 words, no heading)

Lead with a one-paragraph thesis. State what the reader will be able to
do or understand after this lesson. No "in this lesson we will...".
End with a single-sentence hook into the rest of the lesson.

**OPTIONAL — only on lessons flagged for animation in curriculum_map.md
(roughly 15-20 out of ~77 lessons).** Embed an animation right after this
paragraph:
  <Animation name="<exact name from curriculum_map.md>" />

If the lesson is not on the animation list, just write the paragraph and
move on — no Animation tag.

### 2. Real-world example (150-250 words, heading: "## Example" or
"## How this plays out in real markets")

A specific scenario with real tickers and real numbers. US OR Bursa
Malaysia example. Show the concept happening to a concrete instrument.
Cite numbers — entry, exit, percentages, ratios. Don't say "imagine
a stock"; say "Look at NVDA in Q1 2026".

### 3. Common beginner mistake (80-150 words, heading: "## The trap")

Name the specific wrong move a beginner makes here and why it feels
right at the time. Then explain what the correct mental model looks
like instead. This is the lesson's most important paragraph — most
people get this part wrong.

### 4. Ask AMI (one line, no heading)

A `<ChatWith>` callout that invites the reader to ask AMI's relevant
agent about this concept directly. Pick the most-relevant agent for
this lesson:

  <ChatWith agent="<agent_id>" />

### 5. Quiz (heading: "## Quiz", REQUIRED for every lesson)

**Every lesson MUST end with at least one multiple-choice quiz.** Users
can also jump straight to the quiz without reading the lesson body —
the quiz is the assessment surface. So:

- Each lesson has at least 1 multi-choice quiz. Ideally 2-3 for longer
  lessons.
- The LAST quiz must require synthesis, not recall — it should test
  whether the reader understood the body, not just whether they skimmed.
- Quizzes can also work as a standalone learning tool — the
  `explanation` field is what teaches when a "skip-to-quiz" user gets
  it wrong.

  <Quiz
    question="A precise, testable question. Use numbers when possible."
    options={[
      "Plausible distractor that catches a common misconception",
      "Correct answer",
      "Another plausible distractor",
      "Edge-case-looking distractor"
    ]}
    answer={1}                 # zero-indexed; in this example the right answer is options[1]
    explanation="Why the right answer is right AND why the most
                 tempting wrong answer fails. Reference numbers from
                 the lesson body."
  />

For numeric free-response:
  <Quiz
    question="If your account is RM5,000 and your max risk per trade
              is 1%, how much can you lose per trade?"
    answer={50}
    tolerance={0}
    explanation="1% of 5,000 = 50."
  />

### 6. Action task (40-100 words, heading: "## Try it")

One concrete thing the reader does inside the AMI Trade app right now.
Examples:
- "Open Settings → Mandate, set max_drawdown_pct to 20, and see how
  the PM's safety floor message changes when you submit a 30% position."
- "In 1-on-1 with the Market Analyst, paste the ticker NVDA and ask
  'What's the current setup?'"
- "Open the Decision Journal and find an old trade. Ask yourself: would
  the lesson you just read have changed how you sized it?"

### 7. Key takeaway (1-2 sentences, heading: "## Takeaway")

The one thing the reader should remember when they close the app. Make
it portable — something they could say out loud to themselves before
opening a trade ticket.

## MDX components available

- `<Animation name="<catalog_name>" />`
  Renders the named animation. Catalog lives at
  content/animations/. If the name doesn't resolve, a placeholder
  renders so the lesson still works. See curriculum_map.md for the
  per-module animation catalog.

- `<Quiz question="..." options={[...]} answer={N} explanation="..." />`
  Multiple-choice. `answer` is a zero-indexed integer.

- `<Quiz question="..." answer={N} tolerance={X} explanation="..." />`
  Numeric free-response. `tolerance` is absolute. No `options` array.

- `<ChatWith agent="<agent_id>" />`
  Button: "Ask <agent_name> about this". Limit 1 per lesson (part 4
  of the template). Pick the most-relevant agent.

## Frontmatter rules

- `id`: zero-padded 3-digit prefix matches curriculum_map.md.
  Filename = `<id>.en.mdx`.
- `level` = Saiful's pedagogical Level (1-8).
- `module` = the cohesive group within the level (1-12).
- `difficulty` = how hard the content is (1-5), independent of level.
- `track` MUST be one of the 7 enum values. Determined by the
  curriculum map. Drives agent-unlock routing.
- `agent_callouts` MUST match the curriculum map for that lesson ID.
  Tag only the agent(s) this lesson teaches about — not every agent
  loosely mentioned.
- `prerequisites`: real lesson IDs only.
- Dates: use today's date in YYYY-MM-DD for both.

## Quality bar (per lesson)

1. Opens with a thesis paragraph — what the reader will be able to do.
2. Uses at least one specific numeric example with a real ticker.
3. Includes at least one falsification condition for any claim. If you
   say "X is bullish", you must also say "X would invalidate if Y".
4. **Has at least one multi-choice quiz. Last quiz requires synthesis,
   not recall** — users who skip the body and jump to the quiz must
   not pass by guessing.
5. Includes a ChatWith for the most-relevant agent.
6. Includes an Action task tied to a real screen in the app.
7. Ends with a portable Takeaway.
8. Animation is OPTIONAL — include only if the lesson is on the
   curriculum_map.md animation list.
9. Avoids: "as we'll see", "stay tuned", "in the next lesson". Each
   lesson stands alone.
10. AMI naming. Never "the AI", "the model", "the LLM".

## Output format

For each lesson, output a fenced code block with the MDX content.
Use the filename as the code-block language tag:

```mdx filename=content/lessons/014_position_sizing_basics.en.mdx
---
id: "014_position_sizing_basics"
title: "Position sizing basics"
...
---

# Position sizing basics

...
```

Do not output prose between code blocks — just the lessons, one
fenced block each.

---

## What you should write today

[Saiful: edit this section per generation run. The examples below show
the typical scope of one run — 5 to 12 lessons keeps quality tight.]

Examples:

- "Write all 7 lessons in Module 3 (Risk Management): IDs 013-019.
   Reference curriculum_map.md for titles, difficulty, track, and
   agent_callouts. Use today's date."

- "Write Module 8 (Emotional Discipline): IDs 045-051. Module 8 has
   no real numeric examples in the way other modules do — use
   real-trader anecdotes ('an experienced trader on Bursa once...')
   instead. Tag bear_researcher and conservative_debator where
   appropriate per curriculum_map.md."

- "Write the first 6 lessons of Module 1 (What Is the Stock Market?):
   IDs 001-006. Lesson 004 (US markets vs Bursa Malaysia) requires
   one paragraph each on NYSE/NASDAQ session times + currencies and
   Bursa session times + currency. Be specific about KLCI."
```

---

## PROMPT 2 — Daily-challenge bank generator

```
You are writing daily challenges for AMI Trade. Same context as the
lesson prompt (AMI is the brand of the AI, 12 agents, mandate-driven
simulation app, US + Bursa Malaysia markets).

Each challenge is a JSON object. Output a single JSON array per batch.

Schema:

{
  "id": "dc_<YYYY-MM-DD>_<slug>",        // unique
  "type": "predict_the_call" | "read_the_chart" | "spot_the_violation" | "match_the_agent" | "whats_missing",
  "difficulty": 1 | 2 | 3 | 4 | 5,
  "locale": "en",
  "scenario": "<the setup the user reads, 30-120 words; uses real
                tickers + specific numbers>",
  "question": "<the actual question being asked>",
  "options": ["<distractor>", "<correct>", "<distractor>", "<distractor>"],
  "answer": <zero-indexed integer pointing to the correct option>,
  "explanation": "<why the right answer is right, and why the most
                  tempting wrong answer fails. Reference scenario
                  numbers explicitly.>",
  "related_lesson": "<lesson id from curriculum_map.md if applicable, else null>",
  "related_agent": "<agent_id if applicable, else null>",
  "tags": ["<short tags>"]
}

Challenge-type guide:

- predict_the_call: scenario shows facts on a ticker; user picks what
  a specific agent would say. Tag related_agent.
- read_the_chart: scenario describes a chart pattern in words (no
  images); user picks the technical setup. Tag market_analyst.
- spot_the_violation: scenario shows a trade ticket + the user's
  mandate; user picks which compliance rule it broke. Tag
  portfolio_manager.
- match_the_agent: scenario shows a quote/statement; user picks which
  of the 12 agents would have said it.
- whats_missing: scenario shows a Room verdict; user picks which
  agent's input is conspicuously absent.

Quality bar (same as lessons):
- Real tickers only. No "Company X". US + Bursa Malaysia.
- Numbers > adjectives in scenarios.
- Distractors plausible to someone who half-read the relevant lesson.
- Explanations must address why the *attractive* wrong answer fails.
- One challenge per day per locale; aim for ~30 challenges per batch
  (one month).

## What you should write today

Examples:

- "Write 30 daily challenges for June 2026 (dc_2026_06_01 through
   dc_2026_06_30), mix of all 5 types (~6 each), difficulty 1-3,
   locale en. At least 5 must be spot_the_violation referencing the
   safety floor."

- "Write 15 challenges tied specifically to Module 11 (Scam
   Protection). Mix of types but all difficulty 1-2 — the goal is
   that even brand-new users can engage with these and learn to
   recognise red flags. Use IDs dc_2026_07_<n>."

Output a single JSON array.
```

---

## PROMPT 3 — AI Coach Q&A Library generator

The AI Coach Q&A Library is a searchable knowledge base of questions
users typically ask AMI. The Concierge agent draws from this for fast
responses and routing decisions. Daily-challenge text and lesson Q&A
can be sourced from here too.

Each entry is a JSON object. Output a single JSON array per batch.

```
You are writing entries for AMI Trade's AI Coach Q&A Library — a
searchable knowledge base of common user questions and AMI's canonical
answer. Same AMI Trade context as the lesson prompt.

Schema:

{
  "id": "qa_<slug>",                  // unique
  "category": "beginner" | "intermediate" | "psychology" | "scam" | "ai_meta" | "platform",
  "question": "<as a user would phrase it>",
  "short_answer": "<1-2 sentence canonical answer. No fluff.>",
  "long_answer": "<3-6 sentence elaboration. Optional — only if the
                   short answer needs more context.>",
  "related_lessons": ["<lesson_id>", ...],   // from curriculum_map.md
  "related_agents": ["<agent_id>", ...],
  "tags": ["<short tags>"]
}

Tone:
- Direct address. The user is asking; AMI answers.
- Short answer is what AMI says first in a chat.
- Long answer expands only if the short answer would feel curt.
- Reference curriculum lessons when the user should go deeper.

Categories explained:

- beginner: "What is a stock?", "What is a stop-loss?"
- intermediate: "Is this breakout setup valid?", "What could go wrong?"
- psychology: "Am I revenge trading?", "Should I stop trading today?"
- scam: "Is this Telegram group legit?", "Is X broker registered?"
- ai_meta: "Can AMI predict the market?", "Why didn't AMI say what I
  expected?"
- platform: "How do I edit my mandate?", "Where is the Decision Journal?"

Quality bar:
- Each entry answers a question users actually ask, not a question
  the curriculum wants them to ask.
- Short answers must be factually conservative — no claims, no
  predictions, no promises. AMI describes process, not outcomes.
- Psychology entries must not give medical advice. They surface
  patterns + suggest the user pause or review their journal.
- AMI is a TRAINING SIMULATOR, not a financial advisor. Q&A answers
  must never frame AMI as advisory in the regulatory sense. Use
  "AMI's training simulation shows..." / "The training verdict in
  that scenario..." / "AMI's role is to give you practice at...".
  Never: "AMI recommends...", "AMI advises...", "act on AMI's call".
- ai_meta entries especially: AMI is described as a training
  environment for evaluating multi-agent analyst output. Users
  practice; they do not receive advice.

## What you should write today

Examples:

- "Write 50 beginner Q&A entries covering the questions a Module 1-3
   reader would naturally ask. Tag related_lessons from curriculum_map.md."

- "Write 30 psychology Q&A entries for users who have just taken a
   loss. All entries should suggest cooling-off behaviour rather than
   doubling down. Reference Module 8 lessons."

- "Write 20 ai_meta entries — questions users ask about what AMI is,
   what it can/can't do, why it gave a particular verdict. These feed
   the Concierge directly."

Output a single JSON array.
```

---

## PROMPT 4 — Glossary generator

```
You are writing entries for AMI Trade's stock-trading Glossary — a searchable
reference of stock-trading terms with locale-aware definitions. The glossary
is consumed by the Concierge for definition lookups, by lessons via inline
term links, and by the Decision Journal for tooltip surfaces.

## File layout (i18n-aware)

The glossary uses LOCALE-SUFFIXED JSON files. The IDs are stable English
snake_case strings shared across every locale. Each locale file is a JSON
array of term objects.

- content/glossary/terms.en.json     ← English (alpha)
- content/glossary/terms.ar.json     ← Arabic (v1.0)
- content/glossary/terms.ms.json     ← Bahasa Malaysia (v1.0)
- content/glossary/terms.<locale>.json for future locales

For Saiful's first generation run, only the .en.json file is generated.
Translation into AR + MS happens externally (per the CLAUDE.md "translation
is not blocking" rule).

## Schema per entry

{
  "id": "<snake_case_english_id>",     // STABLE ACROSS LOCALES — never translated
  "term": "<localized term>",          // displayed text in this locale
  "definition": "<1-3 sentence definition in this locale>",
  "category": "basics" | "order_types" | "technical" | "fundamental" | "ratios" | "psychology" | "strategy" | "regime" | "macro" | "options_derivatives" | "scam" | "platform" | "advanced",
  "see_also": ["<other_term_id>", ...],         // optional, references other glossary IDs
  "related_lessons": ["<lesson_id>", ...],      // optional, numeric 3-digit IDs
  "related_agents": ["<agent_id>", ...],        // optional, canonical 13
  "tags": ["<short tag>", ...]
}

## Rules

1. **id is stable across locales.** Always English snake_case. Other locale
   files use the same ids. Never translate the id. Example: { "id": "stock",
   "term": "سهم" } in the Arabic file; { "id": "stock", "term": "Saham" } in
   the MS file.

2. **term is localized.** The displayed term in the active locale.

3. **definition is 1-3 sentences in this locale.** Factual, neutral,
   analyst-to-analyst. Avoid marketing words. Avoid "investment advice"
   framing — definitions describe what a term means, never what the user
   should do with it.

4. **Training-frame language (load-bearing — regulatory).** AMI is a training
   simulator, NOT a financial advisor. Definitions describe concepts; they
   never recommend, advise, or suggest action. Use neutral terms: "is a
   technical indicator that measures...", "describes a market state in
   which...". Never: "you should use X when...".

5. **Categories** (use the enum exactly):
   - `basics` — vocabulary a beginner needs (stock, share, exchange, dividend,
     market cap, ticker, brokerage, etc.)
   - `order_types` — order mechanics (market, limit, stop, GTC, IOC, etc.)
   - `technical` — chart-reading terms (candlestick, support, resistance,
     trend, breakout, MA, RSI, MACD, Bollinger Bands, etc.)
   - `fundamental` — company / financial statement terms (revenue, EBITDA,
     FCF, ROE, balance sheet, moat, etc.)
   - `ratios` — specific ratios (P/E, P/B, D/E, dividend yield, etc.)
   - `psychology` — behavioural finance terms (FOMO, revenge trading,
     overconfidence, anchoring, etc.)
   - `strategy` — strategy/system terms (trend-following, mean reversion,
     momentum, backtesting, etc.)
   - `regime` — market-state terms (bull market, bear market, sideways, VIX,
     volatility regime, sector rotation, breadth, etc.)
   - `macro` — macro / news / cycle terms (Fed, rate hike, inflation,
     recession, yield curve, etc.)
   - `options_derivatives` — option/derivative terms (call, put, strike,
     expiry, IV, etc.) — describe the concept only; do not advocate use
   - `scam` — scam pattern names (Ponzi, pump-and-dump, clone broker,
     pig-butchering, etc.)
   - `platform` — AMI-internal terms (Mandate, Verdict, Convene the Room,
     Coach Your Agent, Decision Journal, PM safety floor, etc.)
   - `advanced` — late-curriculum terms (Kelly criterion, walk-forward,
     correlation under stress, etc.)

6. **see_also** references the IDs of related glossary entries. Optional.
   Use it to build a small graph (e.g., "support" sees_also "resistance" and
   "trendline").

7. **related_lessons** references curriculum lesson IDs as zero-padded 3-digit
   strings. Optional. Use only when there's a clean fit.

8. **related_agents** references canonical agent IDs. Optional. E.g., RSI
   sees_also "market_analyst"; "Mandate" sees_also "portfolio_manager".

9. **tags** is a non-empty array of short string tags useful for search and
   filtering (e.g., ["beginner", "vocabulary", "ownership"]).

10. **Coverage target** for the EN v1 batch: ~150-200 entries spanning all 13
    categories. Bias toward terms a Module 1-3 user would naturally encounter
    (basics, order_types, basic technical, key fundamental concepts, common
    ratios), plus all platform terms (so the Concierge can define them).

11. **No outcome promises.** Definitions describe concepts. Never frame
    indicators or strategies as "winning" or "high accuracy". Falsifiability
    framing is fine: "a signal that is invalidated when X".

12. **AMI naming rule.** Never "the AI" / "the LLM" / "the model" / "ChatGPT".
    Use AMI. Agents by role.

## Output format

A single JSON array of term entries. Write it to
content/glossary/terms.<locale>.json. The Saiful-facing run generates
content/glossary/terms.en.json first.

## What you should write today

Examples:

- "Write 180 terms for the EN v1 glossary, spanning all 13 categories.
   At least 25 basics, 20 order_types + technical, 25 fundamental + ratios,
   15 psychology, 15 strategy, 12 regime, 12 macro, 8 options_derivatives,
   12 scam (mirror Module 11), 12 platform (AMI-internal terms), 12 advanced.
   Use today's date if you embed a timestamp in tags."

- "Translate the existing EN glossary to Arabic. Keep ids identical;
   localize term + definition only. Write to content/glossary/terms.ar.json."

- "Add 30 new platform terms covering Coach Your Agent, the safety floor
   internals, and Earn Path mechanics. Save to content/glossary/terms.en.json
   (extend the existing array)."

Output a single JSON array. Validate with `python -m json.tool` before saving.
```

---

## How to land the generated content in the repo

### Lessons

1. Save each fenced MDX block to its filename under `content/lessons/`.
2. Run `pytest backend/tests/unit/ -q`. The lesson loader auto-discovers
   new MDX files; if frontmatter is malformed, `test_lessons_service`
   fails with a clear error.
3. The lesson appears in `GET /v1/lessons` automatically.
4. Verify the animation names referenced in each lesson exist in
   `content/animations/` (or stub them with a placeholder for now —
   the `<Animation>` component renders a placeholder when the name
   doesn't resolve).

### Daily challenges

1. Save the JSON array to `content/daily_challenges/<batch>.json`.
2. The challenge ingestion service (Alpha A17 precursor — not yet
   built) will pick them up.

### AI Coach Q&A Library

1. Save the JSON array to `content/ai_coach/<batch>.json`.
2. The Concierge embedding pipeline (not yet built — likely Beta) will
   ingest these into a vector store for retrieval.

### Glossary

1. Save the JSON array to `content/glossary/terms.<locale>.json` (start with `terms.en.json`).
2. The Glossary loader (not yet built — likely Alpha A18) will pick these up by locale, falling back to `en` for any term missing in the active locale's file.
3. Glossary terms can be linked inline from lessons via `<Term id="<term_id>" />` (component not yet wired — placeholder will render as bold text on miss).
4. Translation pipeline: same `id` set across locale files; only `term` + `definition` change. Saiful arranges external translation; AI-generated translations for AR/MS happen after the EN base ships and stabilises.

---

## Animation catalog reference

Animations live at `content/animations/<name>.json` (Lottie) or as
Flutter-rendered widgets keyed by name. Catalog per module is listed in
`docs/04_education/curriculum_map.md`. Missing animations render a
placeholder; lessons still work without them.

---

## Iteration tips for Saiful

- Run in batches of 5–12 lessons per AI-tool conversation. Context drift
  kills voice consistency past ~10 long lessons in one session.
- Always reference curriculum_map.md for the specific lesson IDs you
  want — the LLM will otherwise invent IDs.
- After each batch, do a `git diff content/lessons/` and spot-check 2–3
  lessons. Common issues: distractors that are obviously wrong, quizzes
  that test recall instead of synthesis, animation names that diverge
  from the catalog.
- For the daily-challenge bank, generate the whole month at once — the
  ID sequence is deterministic so a single batch is easier to audit.
- AI Coach Q&A entries are the highest-leverage content because every
  user hits them via the Concierge. Bias toward more entries per batch
  (50+) but with shorter answers.
