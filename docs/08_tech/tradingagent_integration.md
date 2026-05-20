# TradingAgents Integration

How we wrap the TradingAgents framework. Their code is the reasoning engine; our code is the personalization, safety, and product layer.

## What TradingAgents is

[TradingAgents](https://github.com/TauricResearch/TradingAgents) (mounted at `/Volumes/Extreme Pro/TradingAgent/`) is a multi-agent LLM framework that orchestrates 12 specialized agents through a LangGraph state machine. Given a ticker and analysis date, it produces a trading decision.

We **do not modify** TradingAgents. We wrap it.

## Integration architecture

```
Our backend (FastAPI)
     ↓
TradingAgentsService (our wrapper)
     ↓
Apply mandate overlay to each agent's prompt
     ↓
Apply user_overlay (from Brief Your Agent)
     ↓
Apply safety_floor (on Portfolio Manager only)
     ↓
Pass to TradingAgentsGraph from tradingagents.graph
     ↓
Stream results back through LangGraph callbacks
     ↓
Our backend persists the run and bills credits
```

## The wrapper service

```python
# backend/app/agents/service.py

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

class AgentsService:
    def __init__(self, llm_router, db):
        self.llm_router = llm_router
        self.db = db
    
    async def convene_room(
        self,
        user_id: str,
        ticker: str,
        mandate: Mandate,
        rounds: int = 1,
    ) -> RoomRun:
        # Compose per-agent overlays
        agent_prompts = self._build_agent_prompts(mandate, user_id)
        
        # Configure TradingAgentsGraph with our LLM choices
        config = self._build_config(mandate.plan, mandate.locale)
        
        # Create graph
        graph = TradingAgentsGraph(config=config, debug=False)
        
        # Inject our overlays into each agent's system prompt
        graph.inject_agent_prompts(agent_prompts)
        
        # Run propagation with streaming callbacks
        room_run = RoomRun(
            user_id=user_id,
            ticker=ticker,
            mandate_version=mandate.version,
            started_at=now(),
            status="running",
        )
        await self.db.save(room_run)
        
        # Stream
        async for event in graph.propagate_stream(ticker, current_date()):
            # Emit event to Supabase Realtime channel
            await self._stream_event(room_run.id, event)
        
        # Get final decision
        _, decision = graph.last_result
        
        # Apply safety_floor compliance check (deterministic)
        if decision.action == "APPROVE":
            check = check_mandate_compliance(decision, mandate)
            if not check.passed:
                decision = decision.with_override(
                    action="REJECT",
                    reason=f"Mandate violation: {check.violations}",
                )
        
        # Persist verdict
        room_run.verdict = decision
        room_run.status = "completed"
        await self.db.save(room_run)
        
        # Commit credit charge (was provisional)
        await self.credits.commit(user_id, room_run.id)
        
        return room_run
    
    def _build_agent_prompts(self, mandate, user_id) -> dict:
        prompts = {}
        for agent_id in TWELVE_AGENT_IDS:
            base = load_base_prompt(agent_id)
            mandate_overlay = generate_overlay(agent_id, mandate)
            user_overlay = get_user_overlay(user_id, agent_id)
            
            full_prompt = base + "\n\n" + mandate_overlay + "\n\n" + (user_overlay or "")
            
            # Append safety floor for Portfolio Manager
            if agent_id == "portfolio_manager":
                full_prompt += "\n\n" + SAFETY_FLOOR_BLOCK
            
            prompts[agent_id] = full_prompt
        return prompts
    
    def _build_config(self, plan, locale):
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = self.llm_router.provider_for(plan, locale)
        config["deep_think_llm"] = self.llm_router.model_for(plan, locale, "deep")
        config["quick_think_llm"] = self.llm_router.model_for(plan, locale, "quick")
        config["max_debate_rounds"] = self.llm_router.rounds_for(plan)
        return config
```

## TradingAgents extension points

The TradingAgents framework supports:
- Multiple LLM providers (OpenAI, Anthropic, Google, xAI, DeepSeek, Qwen, GLM, OpenRouter, Ollama, Azure)
- Custom agent prompts via the `inject_agent_prompts` mechanism (we contribute this if it doesn't exist)
- Streaming via LangGraph callbacks
- Checkpoint resume via `--checkpoint` flag
- Decision log via `~/.tradingagents/memory/`

We use all of these. The `inject_agent_prompts` is the key integration — we don't fork TradingAgents to add per-user prompts; we use their config-driven prompt injection.

## What we contribute back

Most useful contributions back to TradingAgents (good open-source citizenship):

| Contribution | Value to upstream |
|---|---|
| Mandate-overlay pattern as a config option | Other users could personalise the agents |
| LangGraph callback hooks for fine-grained streaming | Other UI integrators benefit |
| Compliance-check function (sanitised, generic) | Risk-tolerance enforcement is universally useful |
| Test cases for non-USD markets (when we add Tadawul/Bursa) | Helps the project work in our markets |

## 1-on-1 implementation

A 1-on-1 doesn't use the full graph — it uses a single agent in isolation:

```python
async def one_on_one(
    user_id: str,
    agent_id: str,
    message_history: list[Message],
    user_message: str,
    mandate: Mandate,
) -> AsyncIterator[str]:
    # Build the single agent
    base = load_base_prompt(agent_id)
    mandate_overlay = generate_overlay(agent_id, mandate)
    user_overlay = get_user_overlay(user_id, agent_id)
    
    system_prompt = base + "\n\n" + mandate_overlay + "\n\n" + (user_overlay or "")
    
    # If PM, append safety floor (though 1-on-1 PM is mostly Q&A, not approval — still appended)
    if agent_id == "portfolio_manager":
        system_prompt += "\n\n" + SAFETY_FLOOR_BLOCK
    
    # Pick model based on plan
    model = llm_router.model_for(mandate.plan, mandate.locale, "default")
    
    # Stream
    async for chunk in llm.stream(
        system=system_prompt,
        messages=message_history + [{"role": "user", "content": user_message}],
        model=model,
    ):
        yield chunk
```

The 1-on-1 doesn't engage other agents. The user gets that agent's perspective only.

## Checkpoint resume

TradingAgents supports LangGraph checkpoint resume. We enable this for Convene the Room runs:

```python
config["checkpoint_enabled"] = True
config["checkpoint_path"] = f"/tmp/tradingagents-checkpoints/{user_id}/{room_run_id}.db"
```

If a Room run crashes mid-execution (e.g., LLM provider timeout), the next request can resume from the last successful node instead of starting over. Saves time and LLM cost.

## Memory log

TradingAgents has a memory log at `~/.tradingagents/memory/trading_memory.md` that records past decisions and reflections. We:
- Store this per-user (`/tmp/tradingagents-memory/{user_id}/trading_memory.md`)
- Mount it as a writable volume in Cloud Run
- Periodically snapshot to Supabase Storage for persistence

This gives users the benefit of "team learning over time" — past Room decisions inform future ones.

## Cost considerations

A full Room run with TradingAgents involves:
- 4 Analysts × 1 LLM call each (parallel)
- 2 Researchers × 1–2 LLM calls each
- Research Manager × 1 call
- Trader × 1 call
- 3 Risk Debators × 1 call each (parallel)
- Portfolio Manager × 1–2 calls

Total: ~15–20 LLM calls per Room. We measured rough token counts in [`docs/06_monetization/unit_economics.md`](../06_monetization/unit_economics.md).

To control cost:
- Cheap-tier Rooms use Haiku/Flash for analysts, escalate to Sonnet for Bull/Bear synthesis, escalate to Sonnet for PM
- Mid-tier Rooms use Sonnet throughout
- Premium-tier Rooms use Sonnet for analysts, Opus for Bull/Bear/PM (where reasoning quality most matters)

This selective use of Opus saves us 60% vs running Opus everywhere.

## Cross-references

- Mandate overlays per agent: [`docs/02_agents/mandate_overlays.md`](../02_agents/mandate_overlays.md)
- Safety floor: [`docs/02_agents/safety_floor.md`](../02_agents/safety_floor.md)
- LLM router: [`llm_routing.md`](llm_routing.md)
- Architecture overview: [`architecture.md`](architecture.md)
- TradingAgents source: `/Volumes/Extreme Pro/TradingAgent/` (see their CLAUDE.md)
