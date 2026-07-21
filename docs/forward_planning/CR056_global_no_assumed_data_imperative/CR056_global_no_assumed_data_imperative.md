# CR056 — Global imperative: no LLM may assume data it was not given

**Status:** proposed (BRIEF — architect/build team researches wording + placement + guard and
implements) · **Filed:** 2026-07-21 (AT:R59) · **Source:** Saiful

> Saiful: *"We need to tell the LLM not to assume data that it does not have. This is for all LLM.
> Make the instruction an imperative."* … *"let that be researched by the architect and build
> team. You need to protect the room, and not be a coder."*

---

## What

Add a single, universal, **imperative** instruction to **every** LLM call in the system — not just
the 12 Room agents, but the Concierge, the PM reformatter, and any future LLM surface — directing
the model to use only the data explicitly provided and never to assume, infer, invent, or recall
absent facts. This is the behavioural counterpart to CR055: CR055 *gives* the agents the data they
were missing; CR056 tells every model *not to fabricate* when a datum is absent.

**This CR is the brief. The architect/build team owns the research (final wording, exact placement,
guard test) and the implementation.** The diagnosis below is a head-start, not a mandate.

## Why

The SCHD incident behind CR055 (a new user; the Trader asserted a false 10–15% holding) is one
instance of a general failure: **when the prompt is silent on a fact, the model fills the gap with
an assumption** instead of declining. That pattern is not Room-specific — any LLM surface that
presents facts can do it (fabricated holdings, prices, dates, prior events, ratios). A structural
fix that supplies the data (CR055) closes one hole; a standing behavioural instruction across all
calls is the defence-in-depth for the holes we haven't found yet.

**Honest constraint (must shape the design, per `failure_patterns.md` P2/P4 + CR038):** prompt
instructions are **not controls** — agents ignore even emphatic directives ~70% of the time. So this
imperative is *defence-in-depth, not a substitute for structural guards.* The team should treat it
as one layer and flag any surface where fabrication is high-stakes enough to also need a structural
fix (as CR055 does for holdings). Do not let this CR become the reason a structural fix is skipped.

## Candidate approach (for the team to evaluate — investigation already done, not prescriptive)

- **Single chokepoint found:** every LLM call routes through the gateway facade
  `LLMGateway.stream_chat` ([`app/services/llm_gateway.py:418`](../../../backend/app/services/llm_gateway.py)).
  No caller invokes a provider directly. That one method is also where the `system_prompt` is
  recorded to `llm_audit`, so injecting there means the rule is both applied **and** auditable
  (verifiable the same way CR046's figures were: grep `llm_audit.system_prompt`). This is the
  natural "for all LLM" insertion point.
- **Two caveats the team must respect at that site:**
  1. **Mock provider branches on the lowercased system prompt** (`MockProvider.stream_chat`,
     ~`:154`): it matches agent-id substrings like `"trader"`, `"market analyst"`, `"portfolio
     manager"`. A preamble containing any of the 12 agent-name tokens would mis-route mock
     responses and break unit tests — the wording must avoid them.
  2. **Safety-floor-is-appended-last invariant** (`agent_prompts.build_agent_prompt:77`,
     `append_safety_floor`): the PM's safety floor must remain the last instruction. **Prepend** the
     imperative (system framing) rather than appending, so the floor still dominates recency.
- **Alternative placement:** `build_agent_prompt` covers the 12 agents but **misses** the Concierge
  and the reformatter — so it does not satisfy "all LLM". Gateway-level does. The team decides.
- **Wording:** an imperative, e.g. *"Use only the facts and numbers explicitly provided in this
  prompt. Do not assume, infer, invent, or recall any datum you were not given — holdings,
  positions, prices, balances, dates, or prior events. If a fact you need is absent, say it is
  unavailable or omit the claim; never fill the gap with an assumption."* Final phrasing is the
  team's to settle (tone, length, whether it names the "data block", localisation).

## Acceptance (team confirms)

1. The imperative appears in the system prompt of **every** LLM call — agents, Concierge,
   reformatter — verifiable by reading `llm_audit.system_prompt` across flows after a live batch.
2. A guard test asserts the rule is injected on the shared path (and that a bypass can't ship
   silently — the CR040 "config/feature dark for months" class).
3. **No regression:** mock-provider routing and the full unit suite stay green (886 today); the
   preamble contains no agent-name token.
4. Honest effect note: if practical, re-run a repro (SCHD-style new-user convene) and report whether
   the instruction alone changes the phantom-data behaviour — measured, not assumed. Expect partial
   effect (CR038); pair with CR055's structural fix for the holdings case.

## Out of scope

- The structural holdings injection (that is CR055).
- Rewriting individual agent base prompts (unless the team finds a per-agent conflict with the
  global rule).

## Governance

Commit tag `(AT:R<N> CR056)`. Complements **CR055** (supply the data) and **CR040** (degrade
loudly); governed by the **CR038 / failure_patterns P2/P4** reality that prompt instructions are
soft controls. Architect/build team implements; this session (protect-the-Room lane) files the brief
and reviews the result.
