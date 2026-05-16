---
folder: 05_agent_alignment
purpose: Audit — do each agent's base prompts match the data actually injected at runtime?
scope: Read-only research. No production code modified. All output stays in Silent_Scout/.
---

# 05_agent_alignment — Agent Prompt × Data Feed Audit

The app's moat is 12 distinct specialist analysts. Each agent has a base prompt
(`content/agents/{id}.md`) that describes what data it expects to receive — MACD,
news feeds, Reddit sentiment, portfolio state, etc. In practice the backend injects
a single shared data structure into every agent's system prompt, in both Room and
1-on-1 modes. This folder documents whether those two things match.

## Files

| File | What it contains |
|---|---|
| `agent_data_matrix.md` | Master table: 12 agents × {prompt claims, Room feed, 1-on-1 feed, gap rating} |
| `gap_analysis.md` | Narrative analysis: severity ratings + actionable recommendations per gap |
| `validation_suite/` | Automated pytest suite that catches regressions when the data pipeline changes |

## How to run the validation suite

```bash
# From repo root
python -m pytest Silent_Scout/05_agent_alignment/validation_suite/ -v
```

No network calls. No LLM calls. Pure static analysis against the prompt files and
a JSON fixture representing the Room profile. The suite will flag whenever a field
a prompt references is absent from the injected data.

## What "gap" means here

- **✅ Covered** — every data field the prompt explicitly names exists in the injected block.
- **⚠️ Partial** — some named fields exist; others are absent or are a coarser proxy.
- **❌ Missing** — the prompt names a data source that is not injected at all.
- **N/A** — the mode doesn't apply to this agent (e.g., Tier-2+ agents only run in Room).

## Structural vs accidental gaps

**Structural** — the app is simulation-only; no Bloomberg terminal, no real Reddit
scraper. The prompt describes what the agent *would* have in a live system.
These gaps are by design and are documented for transparency, not flagged as bugs.

**Accidental** — the data exists somewhere in the pipeline but isn't routed to the
agent. These are bugs and come with specific fix recommendations in `gap_analysis.md`.

## Source files read (not modified)

- `content/agents/*.md` — 13 base prompts (12 trading agents + Concierge)
- `backend/app/services/room_runner.py:185–272` — `_profile_for_ticker()`
- `backend/app/services/room_prompts.py:136–173` — `_format_profile()`
- `backend/app/services/agent_runner.py:128–145` — 1-on-1 live-data injection
- `backend/app/services/fundamentals.py:138–174` — `build_live_data_block()`
