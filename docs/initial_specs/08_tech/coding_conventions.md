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

### Reading a claim out of agent prose (CR144)

Any regex or parser that reads a value or a claim out of LLM-authored text must
carry a comment at its definition site naming **the structured field that was
considered instead, and why it lost**. If no such field exists, say that — and
say whether making one is cheaper than the parser.

*Why.* Every prose checker we have written is a missing field until proven
otherwise, and the proof is cheap only before the parser exists:

- **DEF231** — six audit rounds and one live defect for a check that compares
  two numbers. Its own filing row specified the fix as a comparison against
  *"a structured number the verdict carries… without parsing free text"*; a
  general prose parser was built instead, and **all four of its defects were
  figures that were not levels of the run at all** (`we'd pay $52.30`; a second
  sentence's level; `$1.00` truncated out of `$1,073.46`, which shipped).
- **DEF235** — the same shape one function over. `\bsize\b` followed by a
  number matched *"a MEDIUM size entry at $188.62"*, and AMI published a
  drawdown contribution **63× too large** under the words "These are the figures
  of record."
- **CR106 B1** — the lesson learned once already and not generalised: level
  provenance was disclosed by appending a sentence to `reason`; the fix was to
  move it into a typed field.

*The law behind the rule.* A prose pattern's false-positive surface is
proportional to how much **wider than the structured answer** it is. So build
the structured half first and let the prose half cover only what the structured
half genuinely cannot reach — usually grammar, which no field can supply. Both
halves are often needed; the order is what is not optional.

*Why a comment and not a lint rule.* The failure is never that someone wrote a
pattern — it is that nobody asked the question. A comment forces it at the one
moment the answer is cheap, and it is reviewable: an auditor can ask "is that
really why it lost?" and the answer is in front of both of you. A lint rule
would be satisfied by boilerplate.

Then ship it under **failure pattern P16** — corpus sweep *and* adversarial
construction, both, plus the extraction-set diff.

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

---

## Commit messages

Conventional-commits prefix + a governance tag. Format:

```text
type(scope): summary (AT:R<N> [CR### | DEF###])
```

- **type** — `feat` · `fix` · `chore` · `refactor` · `style` · `docs` · `test`.
- **`AT:R<N>`** — the session tag (`project_prefix` + track + session number, from
  `.claude/session-config.yml`). `R` = Development, `M` = Marketing.
- **`CR###` / `DEF###`** — the governance ID (see
  [Change governance in `CLAUDE.md`](../../../CLAUDE.md) and the registers under
  [`docs/forward_planning/`](../../forward_planning/cr_list.md) /
  [`docs/defect/`](../../defect/def_list.md)). Every behaviour-changing commit carries one.

Special cases:

- **User-reported bug fix** — keep the short-id prefix so `git blame` points at the report,
  and add the DEF tag: `fix(bug:<short-id>): summary (AT:R<N> DEF###)` (the first 8 chars of
  the `bug_reports.id` UUID). This is what [`/fix-bugs`](../../../.claude/commands/fix-bugs.md) emits.
- **Exempt from needing a CR/DEF id** — keep the plain `(AT:R<N>)` tag: handover wraps
  (`chore(handover): wrap AT:R<N>`), TestFlight/build version bumps, and docs-only commits.

Examples:

```text
feat(journal): filter entries by trade vs room (AT:R42 CR007)
fix(bug:a84361f6): Apple sign-in 503 glitch (AT:R37 DEF033)
refactor(docs): move spec tree under docs/initial_specs/ (AT:R48 CR001)
chore(mobile): bump build 0.1.0+33 → 0.1.0+34 for TestFlight
```
