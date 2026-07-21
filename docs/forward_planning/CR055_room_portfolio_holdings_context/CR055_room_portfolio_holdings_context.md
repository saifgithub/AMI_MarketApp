# CR055 — Inject the user's real portfolio holdings into every Room agent prompt

**Status:** proposed · **Filed:** 2026-07-21 (AT:R59) · **Source:** Saiful (live incident: a new
user convened the Room for SCHD; the Trader refused to buy, asserting the user "already holds a
10–15% allocation" — false, the user held nothing)

---

## What

Every agent in "Convene the Room" is told, in its role prompt, *"You know: the user's current
portfolio + remaining drawdown capacity."* **No agent is actually given the holdings.** The only
holdings block that exists is gated on a linked Alpaca paper account, which most users — and every
brand-new user — do not have. So the agents operate blind on holdings while being told they can see
them, and they invent positions.

This CR makes the Room **always** inject the user's real holdings, sourced from the **sim engine**
(the app's portfolio of record — simulation-only, no brokerage), with an explicit, unambiguous
statement of *"no open positions"* for a new/empty user. It also closes the secondary coherence gap
that supplied the specific bad number in the incident: the researchers propose position sizes far
above the enforced single-name cap.

## Why — the incident (measured, from `llm_audit` on melehost)

New user `d00000f5…` convened SCHD (2026-07-21 17:24 UTC, `llm_audit` id
`d594f408-c533-4dc2-ba4c-e180d53cdb76`). The Trader's response:

> *"I cannot execute a new BUY order for SCHD … because the user's portfolio **already holds a
> 10–15% allocation**, and this mandate enforces a **long_only** constraint that prevents holding
> two opposing or duplicate entries in the same instrument. I will instead propose a **HOLD** …"*

The user held **nothing**. Trace of the failure:

1. **The "10–15%" came from the transcript, not any portfolio record.** The Bull Researcher
   (*"Sizing Suggestion: allocate 10–15% of the portfolio"*) and the Research Manager (*"a 10–15%
   position size"* / *"Allocate 10–15% as a core dividend anchor"*) both **proposed** that size for
   a *new* buy. The Trader read a *proposed* size as an *existing* holding.
2. **Root cause — the prompt promises portfolio knowledge and delivers none.** The base Trader/PM
   prompt (`app/services/agent_prompts.py`) claims *"You know: the user's current portfolio"*. The
   only holdings block, `alpaca_snapshot`, is injected in `room_runner.py:1300-1312` **only if**
   `urow.alpaca_access_token` is set. A new user has no token → `alpaca_snap = None` → **zero
   holdings data in the prompt**. The model resolves the promise-vs-silence contradiction by
   fabricating a holding, and the only allocation figure on the table was the researchers' 10–15%.
3. **The real portfolio was right there, unused.** The convene entrypoint already computes
   `portfolio_value = sim.total_value(user_id)` (`api/room.py:162`, `api/mandate.py:263`) from the
   sim engine, but only the aggregate *number* is passed into `_RoomContext`; the **holdings list is
   never rendered into any prompt** (no `sim.list_trades`/positions call anywhere in
   `room_runner.py`).
4. **Downstream compounding (not a separate cause):** the Trader also misread `long_only` as
   forbidding "duplicate entries" — `long_only` only forbids shorts. That misfire rode on top of the
   phantom holding.

This is the **CR040 "degrade loudly / prompt-promises-vs-data" class** and a sibling of the CR046
doctrine (*the number an agent is shown must equal the number the system holds*): here the agent is
shown a *claim of knowledge* the data never backs.

## Secondary defect — researchers size above the enforced cap (source of the bad number)

The Bull Researcher and Research Manager suggested **10–15%**, but the enforced single-name cap is
**3.0%** for `risk_score=3` (stated in the Trader's own prompt via CR046 M03). Their prompts don't
carry the M03 `risk_tier_cap`, so they routinely propose sizes ~4× what the system enforces — an
oversized, un-anchored figure that is both wrong on its own terms and easy to mistake for a position.
Fixing this removes the specific "10–15%" that triggered the hallucination **and** restores
shown==enforced coherence for the two research agents (extends CR046 M03 to the researcher prompts).

## Scope

### 1. Always inject a real holdings block (the fix)

- Add a sim-sourced holdings snapshot builder (mirroring `alpaca_service.snapshot_text`'s contract)
  that reads the user's **open** positions via `sim.list_trades(user_id, status=OPEN)` + cash /
  `sim.total_value(user_id)`, and renders a compact block, e.g.:

  ```
  --- YOUR SIMULATED PORTFOLIO ---
  Cash: $100,000.00 | Portfolio value: $100,000.00
  Open positions: none — you hold nothing yet. Any BUY here opens a NEW position.
  ---
  ```

  For a user with holdings, list them (`SYMBOL ×qty (weight% of portfolio, unrealised ±$)`), and —
  critically — state the weight of **the ticker under discussion** explicitly (0% when not held), so
  no agent has to infer "do we own this?".
- Inject it for **every** Room agent (it flows through `build_agent_prompt`'s existing snapshot
  slot), **unconditionally** — a new user gets the explicit "none" block, never silence.
- The Alpaca snapshot stays as an *optional overlay* for the minority who linked a paper account; the
  sim block is the always-present source of truth. If both exist, the sim block is authoritative for
  Room reasoning (decide precedence explicitly, don't emit two conflicting portfolios).
- **Degrade loudly:** if the sim holdings fetch fails, say so in the block (*"portfolio unavailable
  this run"*) — never fall back to silence, which is exactly what produced this bug.

### 2. Give the researchers the enforced size cap (M03, coherence)

- The Bull/Bear/Research-Manager prompts must carry the same `risk_tier_cap(risk_score)` figure the
  Trader and PM already see (CR046 M03), phrased as the ceiling their sizing suggestion must respect.
  Removes the 10–15%-vs-3.0% incoherence.

### 3. Tighten the `long_only` wording (small, prevents the downstream misfire)

- Wherever `long_only` is described to agents, state it plainly: *"long-only = no short/negative
  positions. It does NOT forbid buying, adding to, or holding a name."* One sentence; kills the
  "duplicate entries" misreading.

## Out of scope

- Any brokerage/real-trading integration (permanently out — simulation-only, per decision log).
- Reworking the sim engine's trade model or the Alpaca-link feature itself.
- The PM's verdict-number authorship (tracked separately on the CR046 backlog).

## Acceptance

1. **Reproduce → fix the incident.** A convene for a ticker the user does **not** hold shows every
   Room agent an explicit "you hold 0% of `<TICKER>` / no open positions" line; the Trader treats it
   as a NEW position and does not assert an existing holding. Verified on a fresh anon user against a
   known name (SCHD), reading the real prompt back from `llm_audit`.
2. **Held case is honest too.** For a user who *does* hold the ticker, the injected weight matches
   `sim` (shown == held), and the agents reason about adding/trimming against the true figure.
3. **Researcher sizing within cap.** Bull/Research-Manager sizing suggestions no longer exceed the
   `risk_score` cap; a guard test asserts the cap line is present in those prompts (extends the
   CR046 M03 parity check).
4. **No silent-holdings path remains.** A unit test builds the Room messages for a user with no
   positions and asserts the holdings block is present and says "none" (never absent). A fetch
   failure renders the loud "unavailable" line, not silence.
5. Full backend unit suite green (886 today). New guards proven RED before the fix where practical.
6. Live smoke after promotion: the SCHD-style convene by a new user returns a coherent BUY/PASS on
   the merits, with no phantom-holding language.

## Governance

Commit tag `(AT:R<N> CR055)`. Relates to **CR046** (agent math ledger — extends M03 to researcher
prompts; the holdings weight is a shown==held figure), **CR040** (degrade loudly — the prompt
asserted knowledge the data omitted), and the **DEF066/M02** drawdown-context work (same "hand the
agent the finished portfolio figure" pattern). The holdings-block builder and its guard test ship in
one commit per the house rule.
