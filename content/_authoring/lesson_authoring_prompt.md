# Lesson + Q&A authoring prompt

Self-contained prompt for any AI tool (ChatGPT, Claude.ai, Gemini, etc.) to generate AMI Trade lessons + daily-challenge data that drop straight into this repo.

Saiful: paste the **PROMPT** block below into your tool of choice. Adjust the "What you should write today" section at the bottom to scope each generation run (e.g. "5 lessons from the Risk track").

---

## PROMPT

```
You are writing educational content for AMI Trade — a mobile-first,
simulation-only AI trading-education iOS app. The user is the CEO of a
12-agent analyst team named AMI. AMI is the brand name of the AI; the
agents are members of AMI. Never write "the AI" or "the LLM" — say AMI.

## What AMI Trade is

- Simulation-only, advisory-only, forever. No brokerage integration ever.
- The user defines a Mandate (risk tolerance, max drawdown, compliance
  flags like halal/ESG/long-only). Every agent works within the mandate.
- The Portfolio Manager (PM) has a non-coachable safety floor: a
  deterministic compliance check that runs on every trade regardless of
  what AMI says.
- "Convene the Room" runs all 12 agents in a debate that produces a
  Verdict (BUY/SELL/HOLD with size, entry, stop, target, horizon).
- Coach Your Agent lets users shape style/priority of any single agent
  via natural language. Cannot bypass the safety floor.

## The 12 agents (+ Concierge)

Analysts (4): Fundamentals, Market (technical), News, Social Media.
Researchers (3): Bull, Bear, Research Manager (synthesises the debate).
Execution (1): Trader.
Risk Debators (3): Aggressive, Conservative, Neutral.
Governance (1): Portfolio Manager (the safety floor enforcer).
Plus: Concierge (the 13th — onboarding + routing, not part of the trading team).

Agent IDs (use these verbatim in agent_callouts):
fundamentals_analyst, market_analyst, news_analyst,
social_media_analyst, bull_researcher, bear_researcher,
research_manager, trader, aggressive_debator, conservative_debator,
neutral_debator, portfolio_manager, concierge

## Brand voice + tone

- Analyst-to-analyst. The reader is intelligent. No condescension.
- Numbers > adjectives. "A 50% drawdown in a 10% position is a 5%
  portfolio hit" beats "a meaningful loss".
- No marketing puffery. No "amazing", "powerful", "revolutionary".
- Confident without hyperbole. State things; don't sell them.
- Falsifiability is sacred — every claim should be checkable.
- Stories work, but only with specifics. Generic case studies are dead.
- AMI sometimes refers to itself in first person ("AMI's Bear here…").
  The agents speak for themselves: "the Bear Researcher", "the PM".

## Lesson file format

Every lesson is a single MDX file at `content/lessons/<id>.en.mdx`.

Structure:

---
id: "<NNN>_<snake_case_slug>"
title: "Human-readable title"
duration_min: <integer, typically 3–6>
level: <1|2|3|4|5>
track: "<one of: foundations | fundamentals_analysis | technical_analysis | news_macro | sentiment_behaviour | risk_portfolio | edge_process>"
topic: "<short slug, e.g. 'ratios', 'frameworks', 'sizing'>"
prerequisites: ["<lesson_id>", ...]   # snake-case ids; can be []
tags: ["<short tags>", ...]
agent_callouts: ["<agent_id>", ...]    # which agents this lesson teaches; controls unlocks
locale_versions: ["en"]
created_at: "YYYY-MM-DD"
updated_at: "YYYY-MM-DD"
---

# <Lesson title>

<Lesson body — markdown, 300–800 words. Use ##/### subheadings.
Numbered lists for procedures. Bold for key terms on first mention.
Inline numeric examples ("NVDA at $152, TTM EPS $4, P/E = 38").
Optionally include 1–2 `<ChatWith agent="agent_id" />` callouts mid-body
where it makes pedagogical sense to invite the reader to ask AMI's
agent directly.>

## Quiz

<Quiz
  question="A precise, testable question. Numbers when possible."
  options={[
    "Plausible distractor that catches a common misconception",
    "Correct answer",
    "Another plausible distractor",
    "Edge-case-looking distractor"
  ]}
  answer={1}                    # zero-indexed; in this example the right answer is options[1]
  explanation="Why the right answer is right AND why the most tempting wrong answer fails. Reference numbers from the lesson body."
/>

<Quiz ... />   # 1–3 quizzes per lesson; the last is usually the most synthesising

## Frontmatter rules

- `id`: zero-padded 3-digit prefix, snake_case slug. Match the filename
  before `.en.mdx`. Example: `057_atr_based_stops.en.mdx` → id `057_atr_based_stops`.
- `track` MUST be one of the 7 enum values listed above. No new tracks.
- `topic` is free-form but reuse existing values where possible (look at
  the lessons you already see).
- `level`: 1 = anyone literate; 3 = someone who has done the prerequisites;
  5 = expert nuance / advanced framework.
- `agent_callouts` controls the Earn Path. To unlock an agent, the user
  must complete every lesson that lists that agent in `agent_callouts`.
  Tag the agent you're explicitly teaching about. Don't tag every agent
  loosely mentioned — only the ones the lesson is genuinely about.
- `prerequisites`: real lesson ids only. Don't invent ids that don't exist.
- Dates: use today's date in YYYY-MM-DD for both.

## MDX components available

- `<Quiz question="..." options={[...]} answer={N} explanation="..." />`
  Multiple-choice. `answer` is a zero-indexed integer.
- `<Quiz question="..." answer={N} tolerance={0.5} />`
  Numeric free-response. `tolerance` is absolute. No `options` array.
- `<ChatWith agent="<agent_id>" />`
  Renders a button: "Ask <agent_name> about this". Used to invite 1-on-1
  with a specific agent. Limit 1–2 per lesson.

## Curriculum scope

7 tracks × ~18 topics → 300 lessons total. Alpha target: 150.

| Track id                  | Target lessons | What lives here                          |
|---------------------------|----------------|------------------------------------------|
| foundations               | 30             | What is a stock / market / order / etc.  |
| fundamentals_analysis     | 50             | Financials, ratios, valuation, comps     |
| technical_analysis        | 50             | Charts, indicators, patterns, volume     |
| news_macro                | 30             | Macro indicators, Fed cycles, sectors    |
| sentiment_behaviour       | 20             | Crowd psych, sentiment, social signals   |
| risk_portfolio            | 50             | Sizing, diversification, drawdown        |
| edge_process              | 70             | Journaling, post-mortems, mental models  |

## Existing lessons (DO NOT duplicate)

001_what_is_a_stock — Foundations
002_what_is_a_market — Foundations
003_what_is_a_brokerage — Foundations
004_market_order_vs_limit — Foundations
005_what_makes_a_price_move — Foundations
006_reading_a_pe_ratio — Fundamentals analysis
007_what_is_a_chart — Technical analysis
008_news_that_moves_markets — News & macro
009_sentiment_and_the_crowd — Sentiment & behaviour
010_bull_vs_bear_thinking — Edge & process
011_position_sizing_basics — Risk & portfolio
012_the_pm_and_your_mandate — Edge & process
013_research_manager_synthesis — Edge & process

## Quality bar

Each lesson must:
1. Open with a one-paragraph thesis that says what the reader will be
   able to do after reading. No "in this lesson we will...".
2. Use at least one specific numeric example with a real ticker (AAPL,
   NVDA, MSFT, etc.). Made-up tickers are forbidden.
3. Include at least one falsification condition for any claim. If you
   say "X is bullish", you must also say "X would invalidate if Y".
4. End with a quiz that requires synthesis, not recall. The right
   answer should require having understood the body, not just having
   skimmed it.
5. If it teaches about a specific agent, include a `<ChatWith>` callout
   for that agent.
6. Avoid: "as we'll see", "stay tuned", "in the next lesson". Each
   lesson stands alone.
7. Use AMI naming. Never "the AI", "the model", "the LLM".

## Output format

For each lesson, output a fenced code block with the MDX content. Use
the filename as the code-block language tag:

```mdx filename=content/lessons/014_orders_and_slippage.en.mdx
---
id: "014_orders_and_slippage"
title: "Orders and Slippage"
...
---

# Orders and Slippage

...
```

Do not output prose between code blocks — just the lessons, one
fenced block each.

---

## What you should write today

[Saiful: edit this section per generation run. Examples:]

Write 10 lessons from the **risk_portfolio** track, levels 2–3, that
follow on from 011_position_sizing_basics. Cover ATR-based stops,
the Kelly criterion (with warnings), correlation-aware sizing,
single-name caps, sector caps, drawdown discipline, and rebalancing.

Make 2 of them tag `portfolio_manager` in agent_callouts (so they
contribute to unlocking the PM). Make 1 tag `aggressive_debator`,
`conservative_debator`, `neutral_debator` (so it contributes to
unlocking the Risk Debators).

Use today's date for created_at and updated_at.
```

---

## Daily-challenge bank prompt (separate artefact)

After the lessons land, generate daily-challenge data the same way.
Format is JSON, one file per batch. The challenge engine picks one
challenge per day per locale.

### PROMPT

```
You are writing daily challenges for AMI Trade. Same context as the
lesson prompt above (AMI is the brand of the AI, 12 agents, mandate-
driven simulation app).

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
                  tempting wrong answer fails. Reference the scenario
                  numbers explicitly.>",
  "related_lesson": "<lesson id if applicable, else null>",
  "related_agent": "<agent_id if applicable, else null>",
  "tags": ["<short tags>"]
}

Challenge-type guide:

- predict_the_call: scenario shows facts on a ticker; user picks what a
  specific agent would say. Tag related_agent.
- read_the_chart: scenario describes a chart pattern in words (no
  images); user picks the technical setup. Tag market_analyst.
- spot_the_violation: scenario shows a trade ticket + the user's
  mandate; user picks which compliance rule it broke. Tag
  portfolio_manager.
- match_the_agent: scenario shows a quote/statement; user picks which
  of the 12 agents would have said it.
- whats_missing: scenario shows a Room verdict; user picks which agent's
  input is conspicuously absent.

Quality bar (same as lessons):
- Real tickers only. No "Company X".
- Numbers > adjectives in scenarios.
- Distractors must be plausible to someone who half-read the relevant
  lesson — not absurd.
- Explanations must include why the *attractive* wrong answer fails,
  not just why the right one wins.
- One challenge per day per locale; aim for ~30 challenges per batch
  (one month's worth).

## What you should write today

[Saiful: edit per run. Example:]

Write 30 daily challenges, mix of all 5 types (~6 each), difficulty
1–3, locale "en". Use ids dc_2026_06_01 through dc_2026_06_30.
At least 5 challenges must reference the safety-floor mandate
compliance check (spot_the_violation type).

Output a single JSON array.
```

---

## How to land the generated content in the repo

Once you have the MDX files from the AI tool:

1. Save each fenced block to its filename under `content/lessons/`.
2. Run `pytest backend/tests/unit/ -q` — the lesson loader auto-discovers
   new MDX files. If frontmatter is malformed the test for
   `LessonsService` will fail with a clear error.
3. The lesson appears in `GET /v1/lessons` automatically; no other code
   change required.

For daily challenges:
1. Save the JSON array to `content/daily_challenges/<batch>.json`.
2. The challenge ingestion service (not yet built — see Alpha A17
   "Daily briefing flow" precursor) will pick them up.
