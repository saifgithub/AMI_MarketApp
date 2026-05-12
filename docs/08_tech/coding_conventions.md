# Coding conventions

Detailed style rules for the AMI Trade codebase. CLAUDE.md keeps the
one-line summary + the AMI/LLM naming rule (which is behavior-critical
every session); everything else lives here.

---

## Flutter

- **Theme tokens** live in `lib/theme/` and mirror `colors_and_type.css` from the AMI design system.
- **Hex shapes** via `ClipPath` + `CustomPainter`. Flat-topped hexagons. Corner cuts ~10px on mobile.
- **Type ramp**: Inter for body, JetBrains Mono for numbers/labels/buttons (UPPERCASE 0.1em letter-spacing).
- **Dark only.** Canvas `#0f172a`. No light theme.
- **RTL-aware** from day one. `padding-inline`, `margin-inline`, `Directionality` widget tree.
- State management: **Riverpod**. (Decided in [`flutter_implementation.md`](flutter_implementation.md).)

---

## Python backend

- **FastAPI** for the API.
- **Pydantic** for schemas — match the Mandate, Agent, JournalEntry data-model definitions in [`data_model.md`](data_model.md).
- **Async-first.** All LLM and DB calls await.
- **TradingAgents integration**: wrap their `TradingAgentsGraph` in our own service layer (`agents/service.py`) that applies the mandate overlay before propagation.
- **No secrets in code.** Use GCP Secret Manager via env vars.

---

## Naming

- Code identifiers: `snake_case` Python, `camelCase` Dart/Flutter.
- Database tables: `snake_case`, plural (`users`, `mandates`, `agent_runs`).
- Agent IDs: `fundamentals_analyst`, `market_analyst`, ..., `portfolio_manager`. Lowercase snake.

### "LLM" → engineers; "AMI" → users

The AI is named **AMI**. Users never see "LLM" or even "the AI" — they see AMI by name. Engineers writing code can use LLM internally.

| Where | Word |
|---|---|
| Code identifiers (`LLMGateway`, `LLMProvider`, `llm_gateway.py`, `llm_smoke.py`) | **LLM** |
| API routes (`/v1/llm/status`) and log keys (`llm_call_start`) | **LLM** |
| Tests, tech comments, code docstrings explaining architecture | **LLM** |
| HANDOVER.md technical sections | **LLM** |
| Lesson content (`content/lessons/*.mdx`) | **AMI** |
| Agent prompts / mock responses surfaced to users | **AMI** |
| Error sentinels streamed back to the iPhone (`[AMI error: ...]`) | **AMI** |
| App copy (Flutter strings, settings labels, marketing material) | **AMI** |
| External-facing docs / README product framing | **AMI** in product framing, **LLM** in technical specifics |

Rule of thumb: if a human user might read it, say AMI. If a developer is reading code or a route name, LLM is fine. We don't say "the AI" anywhere user-visible — say AMI by name.

---

## Comments

- Default to no comments. Write self-documenting code.
- Add comments only when the *why* is non-obvious (a subtle invariant, a workaround, a hidden constraint).
- Never explain *what* the code does — names should.

---

## File headers

Every new file gets a short docstring / library comment explaining what it is and why.

```python
"""LLM gateway — provider-agnostic interface for the rest of the backend.

Providers are picked at runtime based on which keys are configured.
See app.services.tier_policy for per-(plan, agent) tier decisions.
"""
```

```dart
/// Sim Portfolio screen.
///
/// Shows cash + holdings + total value + P&L + drawdown. Pull-to-refresh
/// triggers a server-side stop/target sweep.
library;
```
