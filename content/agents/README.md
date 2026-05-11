# Agent Base Prompts

One markdown file per agent. Each file is the **base prompt** for that agent — the role definition that ships with the product.

At runtime, the full prompt for any agent is composed as:

```
agent.final_prompt = base_prompt (this file)
                   + mandate_overlay   ← from app/agents/overlay_generator.py
                   + user_overlay      ← from Coach Your Agent (Postgres user_overlays)
                   + safety_floor      ← only on Portfolio Manager, uncoachable
```

The base prompt is the **only part Saiful + Claude write**. It changes rarely. The other layers are dynamic per-user.

## Files

| Agent | File | Color |
|---|---|---|
| Fundamentals Analyst | [fundamentals_analyst.md](fundamentals_analyst.md) | cyan |
| Market Analyst | [market_analyst.md](market_analyst.md) | cyan |
| News Analyst | [news_analyst.md](news_analyst.md) | cyan |
| Social Media Analyst | [social_media_analyst.md](social_media_analyst.md) | cyan |
| Bull Researcher | [bull_researcher.md](bull_researcher.md) | purple |
| Bear Researcher | [bear_researcher.md](bear_researcher.md) | purple |
| Research Manager | [research_manager.md](research_manager.md) | purple |
| Trader | [trader.md](trader.md) | green |
| Aggressive Debator | [aggressive_debator.md](aggressive_debator.md) | amber |
| Conservative Debator | [conservative_debator.md](conservative_debator.md) | amber |
| Neutral Debator | [neutral_debator.md](neutral_debator.md) | amber |
| Portfolio Manager | [portfolio_manager.md](portfolio_manager.md) | purple |
| **Concierge** (13th) | [concierge.md](concierge.md) | pink |

## Frontmatter schema

```yaml
agent_id: snake_case_unique_identifier
display_name: "Human-readable name"
family: analyst | researcher | manager | risk | execution | concierge
role_color: cyan | purple | amber | green | pink
```

## Editing

These prompts are intentionally LIVE — Saiful can iterate on them as agent quality is observed. After editing, the backend hot-reloads them on next request (no restart needed). Use [`docs/02_agents/twelve_agents.md`](../../docs/02_agents/twelve_agents.md) for the agent design references.

Translation: AR + MS variants come at v1.0 as `*.ar.md` and `*.ms.md`. The runtime loader picks the file matching the user's locale.
