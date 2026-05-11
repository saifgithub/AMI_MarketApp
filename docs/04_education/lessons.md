# Trading Fundamentals Lessons

The 300-lesson curriculum (150 at alpha, 300 by v1.0). Always free. Authored as MDX, delivered through an AI-tutor wrapper that adapts to the user's mandate and learning style.

## Curriculum structure

7 tracks → 18 topics → ~300 lessons total. Roughly 3 min per lesson.

| Track | Topics | Lessons (target) |
|---|---|---|
| **Foundations** | What is a stock, market basics, brokerages, orders | 30 |
| **Fundamentals analysis** | Reading financials, ratios, valuation, comps | 50 |
| **Technical analysis** | Charts, indicators, patterns, volume | 50 |
| **News & macro** | Macro indicators, Fed cycles, sector dynamics | 30 |
| **Sentiment & behaviour** | Crowd psychology, sentiment indicators, social signals | 20 |
| **Risk & portfolio construction** | Sizing, diversification, drawdown management, hedging | 50 |
| **Edge & process** | Decision journaling, post-mortems, mental models, biases | 70 |

At alpha we ship the first ~150 (Foundations + half of each other track). The remainder ships gradually toward v1.0.

## Lesson format

Each lesson is a single MDX file:

```markdown
---
id: 003_reading_pe_ratio
title: "The P/E Ratio"
title_ar: "نسبة السعر إلى الأرباح"
title_ms: "Nisbah P/E"
duration_min: 3
level: 1
track: fundamentals_analysis
topic: ratios
prerequisites: [001_what_is_a_stock, 002_intro_to_earnings]
tags: [fundamentals, valuation, ratios]
agent_callouts: [fundamentals_analyst]
locale_versions: [en, ar, ms]
created_at: 2026-04-01
updated_at: 2026-04-15
---

# The P/E Ratio

The price-to-earnings ratio (P/E) is one of the first numbers any 
fundamentals analyst looks at...

[content body in MDX — text + simple component embeds]

## Try it

Here's NVDA's price and last 12 months of earnings per share:
- Price: $152
- TTM EPS: $4.00

What's the P/E? <Quiz answer={38} tolerance={0.5} />

## Want to go deeper?

If you found this useful, the **Fundamentals Analyst** can show 
you how P/E fits into a full valuation. <ChatWith agent="fundamentals_analyst" />
```

## Frontmatter fields

| Field | Type | Notes |
|---|---|---|
| `id` | string | Snake-case unique identifier, e.g. `003_reading_pe_ratio` |
| `title` (+ `title_ar`, `title_ms`) | string | Title per locale |
| `duration_min` | int | Average reading + interaction time |
| `level` | 1–5 | Difficulty |
| `track`, `topic` | string | Curriculum tagging |
| `prerequisites` | string[] | Lesson IDs the user must complete first |
| `tags` | string[] | For search and Concierge routing |
| `agent_callouts` | string[] | Which agents this lesson connects to (offers 1-on-1) |
| `locale_versions` | string[] | Languages available |

## File organisation

```
content/lessons/
├── _index.json                          ← auto-generated catalogue
├── 001_what_is_a_stock.en.mdx
├── 001_what_is_a_stock.ar.mdx
├── 001_what_is_a_stock.ms.mdx
├── 002_intro_to_earnings.en.mdx
├── ...
```

One file per (lesson, locale) pair. At alpha, only `.en.mdx` exists; AR and MS arrive at v1.0.

`_index.json` is generated at build time from the frontmatter — fast lookup, full-text searchable, cached on the server.

## AI-tutor wrapper

When a user opens a lesson, the raw MDX is the **base content**. An AI-tutor wrapper personalises the delivery:

| Input | Used to |
|---|---|
| User's `mandate.learning_style` | Choose tone (quick / story-led / visual / hands-on) |
| User's `mandate.path` | Decide which examples to lead with |
| User's `mandate.compliance` | Use halal-friendly examples for halal users; etc. |
| User's `mandate.locale` | Render in the user's language |
| User's curriculum history | Skip / condense things they've already mastered |
| User's recent Decision Journal entries | Connect lesson to their *actual* trades |

The wrapper produces an *enhanced* lesson:

```
[BASE LESSON CONTENT]
   ↓
[WRAPPER ADDS]
- Opening line that connects to user's mandate
- Examples chosen to match user's path and compliance
- Mid-lesson "what about your portfolio?" callout if relevant
- Closing CTA tailored to user's next-step opportunity
```

### Example — same lesson, two users

**User A** (long-horizon retirement, halal, story-style):

> *"Let's talk about the P/E ratio — it's going to come up every time your Fundamentals Analyst looks at a halal name for your retirement plan. Picture P/E like this..."*

**User B** (active trader, no halal, quick-style):

> *"P/E ratio. Price ÷ earnings. Tells you what the market's willing to pay for each $1 of profit. Higher P/E = more growth priced in. Let's run the numbers on NVDA."*

Same lesson body. Two different doorways.

### Implementation

```python
def render_lesson(lesson_id: str, user: User) -> RenderedLesson:
    base = load_mdx(lesson_id, user.mandate.locale)
    wrapper_prompt = build_wrapper_prompt(
        learning_style=user.mandate.learning_style,
        path=user.mandate.path,
        compliance=user.mandate.compliance,
        curriculum_history=user.curriculum_progress,
        recent_journal=user.recent_journal_entries(days=30),
    )
    # LLM call to wrap the lesson
    wrapped = llm_call(wrapper_prompt + base, model="cheap_tier")
    return wrapped
```

Wrapping uses the **cheap-tier model** because the base content is correct — we just need stylistic adaptation. Costs ~$0.001 per lesson load.

### Caching

Same (lesson_id, locale, learning_style, path, top-3 compliance flags) combination → cache the wrapped output. Most users hit the cache. Cache TTL: 24 hours.

## Quizzes (AI-generated)

Each lesson ends with 1–3 quiz questions. The MDX defines:

```markdown
<Quiz 
  question="What does a high P/E ratio typically indicate?" 
  options={[
    "Strong recent earnings",
    "Expected future growth",
    "Low stock price",
    "Industry leadership"
  ]}
  answer={1}
  explanation="A high P/E means investors are paying more per dollar of current earnings — usually because they expect earnings to grow faster than peers."
/>
```

For **adaptive quizzing**, the wrapper can also generate *new* questions based on the user's gap profile — questions the user is most likely to get wrong, surfaced just-in-time.

## Remedial micro-lessons on quiz fail

If a user fails a quiz question:

1. The wrapper analyses *which concept* they missed
2. Generates a 60-second remedial micro-lesson on that concept
3. Quiz the user again
4. If they pass, they continue with the next lesson
5. If they fail twice more, Concierge offers a 1-on-1 with the relevant analyst

Failed concepts are stored in the user's gap profile and informed future curriculum recommendations.

## Curriculum progression

The Concierge tracks each user's progress and recommends next lessons. Users are not forced into a linear path — they can:
- Follow the recommended next
- Browse by track
- Search by topic
- Tap an agent callout from anywhere → routes to a relevant lesson

## Lesson authoring at MVP

| Activity | Who |
|---|---|
| Drafting lessons (EN) | Claude — I write all 150 lessons at alpha |
| Reviewing lessons (EN) | Saiful — reviews and approves before publication |
| Translation to AR + MS | Saiful arranges externally (v1.0) |
| Native-speaker QA | Saiful arranges (v1.0) |
| Quiz question authoring | Claude initially; AI-generated adaptive quizzes Phase 2 |

**At alpha:** 150 EN lessons. Manageable.
**At v1.0:** 300 EN + 300 AR + 300 MS = 900 lesson files. Translation pipeline kicks in.

## Authoring CMS (Phase 2)

Per Saiful's decision: no CMS at MVP. Lessons are static MDX in the repo. If the app takes off, Phase 2 brings:

- Web-based authoring tool (likely Sanity or Decap headless CMS)
- AI-assisted draft generation (LLM drafts → human reviews → publish)
- Approval workflow
- Versioning of published lessons
- Author analytics (which lessons are most opened, where users drop off)

## Cross-references

- AI-tutor wrapper details: see implementation pattern above
- Concierge lesson routing: [`docs/02_agents/concierge.md`](../02_agents/concierge.md)
- Pluggable i18n: [`docs/07_localization/i18n_architecture.md`](../07_localization/i18n_architecture.md)
- Agent Academy modules (separate curriculum): [`agent_academy.md`](agent_academy.md)
