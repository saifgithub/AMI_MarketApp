# TradingAgents Integration

How we wrap the TradingAgents framework. Their code is the reasoning engine; our code is the personalization, safety, and product layer.

> **Alpha status:** the alpha Room uses a standalone scripted orchestrator (`RoomRunner`) with deterministic agent templates — TradingAgents graph is **not yet wired**. The architecture and code sketches below document the target design. The single-function swap to live LLM is noted where it applies.

## What TradingAgents is

[TradingAgents](https://github.com/TauricResearch/TradingAgents) (mounted at `/Volumes/Extreme Pro/TradingAgent/`) is a multi-agent LLM framework that orchestrates 12 specialized agents through a LangGraph state machine. Given a ticker and analysis date, it produces a trading decision.

We **do not modify** TradingAgents. We wrap it.

## Integration architecture

### Alpha (current)

```
Our backend (FastAPI)
     ↓
RoomRunner  (backend/app/services/room_runner.py)
     ↓
build_room_messages()  (services/room_prompts.py)
  → base prompt per agent
  → mandate overlay   (generate_overlay)
  → user brief overlay  (_append_user_overlay)
  → safety_floor block  (portfolio_manager only)
     ↓
Scripted _TEMPLATES dict  ← alpha placeholder
(one deterministic response per agent per ticker)
     ↓
check_mandate_compliance()  ← deterministic, always runs
     ↓
Stream SSE events to Flutter client
```

### Planned (post-alpha)

```
RoomRunner
     ↓
build_room_messages()  (same prompt pipeline)
     ↓
TradingAgentsGraph.propagate()  ← swap in here
     ↓
Stream LangGraph callbacks → SSE events
```

The scripted `_TEMPLATES` block in `room_runner.py` is the only thing standing between alpha and live LLM. Everything else — prompt composition, safety floor, SSE streaming, dedup, background-task queue — is already production-grade.

## The wrapper service — current

```python
# backend/app/services/room_runner.py

class RoomRunner:
    """Orchestrates a Convene the Room session.

    start_run()  — public entry: reserves a room_run row, enqueues
                   background task, returns run_id immediately.
    run()        — async generator: does the work, emits SSE events.
    """

    async def start_run(
        self,
        user_id: UUID,
        ticker: str,
        session: AsyncSession,
    ) -> str:  # returns room_run_id
        ...

    async def run(
        self,
        room_run_id: str,
        user_id: UUID,
        ticker: str,
        mandate: Mandate,
    ) -> AsyncIterator[dict]:
        # Alpha: iterate _TEMPLATES[ticker] entries
        # Planned: graph.propagate(ticker, analysis_date)
        ...
```

## Prompt composition

Prompt building for Room lives in `backend/app/services/room_prompts.py`:

```python
# backend/app/services/room_prompts.py

def build_room_messages(
    agent_id: AgentId,
    mandate: Mandate,
    user_id: UUID,
    message_history: list[dict],
    user_message: str,
) -> list[dict]:
    """Returns the full messages list for one agent call."""
```

Prompt building for 1-on-1 lives in `backend/app/services/agent_prompts.py`:

```python
# backend/app/services/agent_prompts.py

def build_agent_prompt(
    agent_id: AgentId,
    mandate: Mandate,
    user_id: UUID,
) -> str:
    """Composes base + mandate overlay + user brief overlay + safety floor (PM only)."""

def _append_user_overlay(prompt: str, agent_id: AgentId, user_id: UUID) -> str:
    """Private helper — looks up active Brief overlay for this user+agent, appends it."""
```

The user brief overlay lookup is internal to `build_agent_prompt` via `_append_user_overlay`. There is no public `get_user_overlay()` function.

## Mandate compliance check

```python
# backend/app/agents/safety_floor.py

def check_mandate_compliance(
    proposed: ProposedTrade,
    portfolio_value: float,
    current_drawdown_pct: float,
    mandate: Mandate,
    *,
    halal_universe: set[str] | None = None,
    locale_allowed_universe: set[str] | None = None,
) -> ComplianceResult:
    """Deterministic mandate-compliance check. No LLM.

    Returns ComplianceResult(passed: bool, violations: list[str], blocked_by: str | None).
    """
```

Called after the Room verdict is produced. If the PM output violates the mandate, the decision is hard-overridden to REJECT before persisting.

## Model tier routing

Per-(plan, agent) tier selection is in `backend/app/services/tier_policy.py::pick_tier()`. It maps `(plan, agent_id)` → `cheap | mid | premium` tier, which the LLM gateway resolves to a specific model. The gateway preference chain is `vllm > anthropic > mock`.

## TradingAgents extension points

The TradingAgents framework supports:
- Multiple LLM providers (OpenAI, Anthropic, Google, xAI, DeepSeek, Qwen, GLM, OpenRouter, Ollama, Azure)
- Custom agent prompts via the `inject_agent_prompts` mechanism (we will contribute this if it doesn't exist upstream)
- Streaming via LangGraph callbacks
- Checkpoint resume via LangGraph's built-in checkpointer
- Decision log via `~/.tradingagents/memory/`

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
# backend/app/services/agent_runner.py

async def stream_one_on_one_message(
    agent_id: AgentId,
    message_history: list[dict],
    user_message: str,
    mandate: Mandate,
    user_id: UUID,
    plan: str,
) -> AsyncIterator[str]:
    # Compose full system prompt (base + mandate overlay + user brief overlay + safety floor)
    system_prompt = build_agent_prompt(agent_id, mandate, user_id)

    # Pick model via tier policy
    tier = pick_tier(plan, agent_id)
    model = llm_gateway.model_for(tier)

    # Stream
    async for chunk in llm_gateway.stream(
        system=system_prompt,
        messages=message_history + [{"role": "user", "content": user_message}],
        model=model,
    ):
        yield chunk
```

The 1-on-1 doesn't engage other agents. The user gets that agent's perspective only.

## Checkpoint resume (planned)

TradingAgents supports LangGraph checkpoint resume. We plan to enable this for Convene the Room runs once TradingAgents is wired:

```python
# Planned — not active in alpha
config["checkpoint_enabled"] = True
config["checkpoint_path"] = f"/tmp/tradingagents-checkpoints/{user_id}/{room_run_id}.db"
```

If a Room run crashes mid-execution (e.g., LLM provider timeout), the next request can resume from the last successful node instead of starting over. Saves time and LLM cost.

## Memory log (planned)

TradingAgents has a memory log at `~/.tradingagents/memory/trading_memory.md` that records past decisions and reflections. Plan:
- Store this per-user (`/tmp/tradingagents-memory/{user_id}/trading_memory.md`)
- Mount it as a writable volume in Cloud Run
- Periodically snapshot to Supabase Storage for persistence

Not active in alpha.

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
