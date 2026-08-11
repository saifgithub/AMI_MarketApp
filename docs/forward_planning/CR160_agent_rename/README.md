# CR160 — Rename six agent roles away from the TradingAgents lineage

**Status:** proposed · **Filed:** 2026-08-09 · **Category:** quality

## Why

The Room's agent graph is inherited from TradingAgents — four analysts → bull/bear +
research manager → trader → three risk debators → PM is that project's figure 1. The
architecture is Apache-2.0 at ★96k (measured 2026-08-08) and is not defensible IP; anyone
can rebuild it. Everything we added on top — mandate overlay, Brief Your Agent, the
deterministic safety floor, the Decision Journal — is **invisible when it works**, so the
surface answer to "what is this?" is still TradingAgents' answer.

Renaming buys surface distinctiveness, not architectural differentiation. That is worth
stating plainly so this CR is not over-valued: the lineage stays recognisable to anyone
comparing graphs. It is worth doing anyway for three reasons that stand on their own —
a spelling bug in shipped copy, a translation problem that gets more expensive at v1.0, and
two names that misdescribe a simulation-only product.

Saiful, 2026-08-08: *"Change the debators, portfolio managers, traders, market analysts, soc
meds, and news analysts. Keep bull and bears, they are market jargons. But yes, we will use
your suggestions for the AR/MS."*

## What changes

| Current | New | Abbrev | Rationale |
|---|---|---|---|
| Aggressive Debator | **Risk Officer — Aggressive** | `AGG` | "Debator" is not a word — see below |
| Conservative Debator | **Risk Officer — Conservative** | `CON` | |
| Neutral Debator | **Risk Officer — Balanced** | `BAL` | |
| Portfolio Manager | **Chief Investment Officer** | `CIO` | The user is CEO; CIO is the natural direct report. "Portfolio Manager" also implies managing real money, which we never do |
| Trader | **Execution Desk** | `EXEC` | We never execute a trade. "Trader" is off-posture for a simulation-only product |
| Market Analyst | **Technical Strategist** | `TECH` | "Market Analyst" is vague; this is the real desk title |
| Social Media Analyst | **Flow & Positioning** | `FLOW` | Ages better — "social media" will read dated within a few years |
| News Analyst | **Macro & Events** | `MACRO` | "News" undersells macro and catalyst coverage |

**Unchanged:** Fundamentals Analyst · Bull Researcher · Bear Researcher · Research Manager ·
AMI Concierge. Bull/Bear stay because they are genuine market jargon, not TradingAgents
coinage.

`role_color` and `AgentFamily` are untouched.

### The spelling bug

"Debator" is not an English word; the correct spelling is "debater". It appears in
user-visible copy across 272 files. The rename removes the word entirely, so **no separate
DEF is needed** — this CR subsumes it.

### AR / MS localisation — transcreation, not translation

Bull/Bear survive in EN as jargon. They do **not** survive translation: rendering them
literally into Arabic (ثور / دب) or Malay produces an animal, not a market stance. The
localised strings therefore use the **Long-Side / Short-Side** concept instead:

| EN | AR / MS concept |
|---|---|
| Bull Researcher | Long-Side Analyst |
| Bear Researcher | Short-Side Analyst |

This is a deliberate divergence from the EN source. **The i18n string files must carry a
context comment saying so**, or the first translator who reads it will "correct" it back to
the literal animal. This is the single highest-risk detail in the CR.

## Scope

**In:**

- `mobile/lib/models/agent.dart` — the client-side registry (`displayName`, `abbreviation`).
  This one file is the whole client surface.
- `backend/app/schemas/agents.py` — the backend mirror.
- `content/agents/*.md` — `display_name` frontmatter on the affected prompt files, and any
  in-prompt cross-references ("That's the Trader's job", "redirect to the Portfolio Manager").
- `content/` at large — **3,348 occurrences** measured 2026-08-08 across lessons, daily
  challenges, glossary and ai_coach.
- `website/` + `website_api/` — 21 occurrences.
- i18n string files, with the transcreation note above.

**Out:**

- **`agent_id` is not touched.** It is a database key with unique constraints across five
  tables — `user_overlays`, overlay counts, activations and two more
  ([`backend/app/db/models.py:286-410`](../../../backend/app/db/models.py#L286-L410)) — and
  Brief Your Agent history is keyed on it. Renaming it is a data migration with no user
  benefit. `aggressive_debator` stays as an identifier forever; only its label changes.
- File names under `content/agents/` stay as-is for the same reason.
- Any behaviour change. Prompts keep their content; only names and cross-references move.

## Sequencing

Land this **before** CR159. Both edit `mobile/lib/models/agent.dart`; doing CR159 first means
redoing every band label.

## Open decision

**Flow & Positioning** is the correct desk term but a beginner will not parse it, and this is
a teaching product. **Sentiment & Flow** keeps a familiar word while still moving off "Social
Media". Defaulting to Flow & Positioning per the instruction above; flag for Saiful before
the content sweep, since changing it afterwards means re-running 3,348 substitutions and
re-flagging translation.

## Translation impact

`content/daily_challenges/ms/` already exists, so this triggers **MS re-translation** per the
standing content rule; AR has not started, which is why doing this now is cheaper than at
v1.0. Every touched content `id` must carry `retranslate:[ar,ms]`.

## Acceptance

- No occurrence of `Debator`, `Portfolio Manager`, `Trader`, `Market Analyst`,
  `Social Media Analyst` or `News Analyst` as an agent label anywhere in `mobile/lib`,
  `content/`, `website/`, `website_api/` or `content/agents/*.md`.
- `agent_id` values are byte-identical before and after; a diff of the ID column proves it.
- Existing Brief Your Agent overlays still resolve to their agents after the change —
  verified against real rows, not a fixture.
- Every touched content id carries `retranslate:[ar,ms]`.
- i18n files carry the Bull/Bear transcreation note.
- `pytest backend/tests/unit/ -q` and `flutter test` both green.
- Release build to device: the Floor, the Verdict Board comb, and one Room run all render the
  new labels with no truncation at 390pt.

---

## Upstream did the same rename, for a different reason (CR167, 2026-08-11)

TradingAgents renamed `social_media_analyst` → `sentiment_analyst` in `0fcf136` — not for
distinctiveness but because the old name described a job the runtime could not do: the prompt demanded
social-media analysis with only a Yahoo news tool behind it, and models *"fabricate Reddit/X/StockTwits
content under prompt pressure (verified live)"*. That is our own DEF063/CR024, reached independently.
Our `content/agents/social_media_analyst.md` still carries the old name, so this CR's rename and that
observation land on the same file.

Second item for this CR's i18n half: upstream **widened** `get_language_instruction()` from
analysts-and-PM to *every* agent whose output reaches the saved report — reversing their earlier
position that internal debate agents should stay English "for reasoning quality" — because a non-English
run otherwise *"produces a fully localized report rather than a mix of languages"*. AR + MS at v1.0 face
that same tradeoff, and it should be decided deliberately rather than inherited.

Detail: [../CR167_tradingagents_upstream_drift/](../CR167_tradingagents_upstream_drift/) §3.1, §6.3.
