# CR104 — Delete the synthetic numeric baseline from the production Room path

**Filed:** 2026-07-27 · **Track:** AT:R59 (room-quality) · **Kind:** CR (structural)
**Source:** Saiful, on reading DEF123 — *"This must be like the 5th time we try to limit the AI from
hallucinating"*

---

## He is right, and the register undercounts him

`failure_patterns.md` already carries **10 instances** across the two fabrication patterns, before
today's three:

- **P2 — silent confident degradation:** DEF063, DEF059, DEF058, CR037, CR038
- **P5 — LLM asked to compute a number it presents as fact:** DEF052, DEF066, CR046 M03, DEF077,
  the CR046 audit sweep

Add DEF123 / DEF124 / DEF125 and it is **13**. So the count is right. But "we keep failing to stop
the AI hallucinating" is the wrong diagnosis, and that is why the fixes keep not sticking.

## The two mechanisms, and which one we've actually been fixing

**Mechanism A — the model invented a number.** DEF066, DEF077, CR046 M03/M06/M08, DEF095, and
today's DEF124. Fix shape: compute it in Python, inject the finished figure, guard it with a test.

**This one is working.** CR046's math ledger is real, `trading_math/` is portable and tested, the
coherence tests (`test_position_sizing.py`, `test_safety_floor.py::…prose_cap_equals_the_enforced_constant`)
pin shown-equals-enforced, and DEF095 was fixed, independently audited, and integrated. P5 has a
named enforcing check and a house rule. Mechanism A is under control.

**Mechanism B — *we* fabricated the number and told the model it was real.** DEF052, DEF063,
CR037, CR038, and now DEF123. In every one of these the model did **exactly what we asked**: it
used only the numbers in its prompt, as the grounding directive demands. The failure is upstream of
the LLM entirely.

**This one we have never fixed.** Every mechanism-B response so far has been *a better label on
the fake data*:

- CR037/CR038 → a disclosure line saying the sentiment/macro fields aren't real
- DEF052 → real technicals for Market, but the rng block left in place underneath
- DEF063 → the config parity test, so the key gets forwarded — the scaffolding stayed
- **DEF123 → the label itself was the lie.** The disclosure header said "LIVE from Yahoo Finance"
  over an rng P/E, in 21.1% of live-declared prompts across 36 tickers.

P2's own entry admits it: *"Enforcing checks. **Partial** … CR037 / CR038 → **no guard yet, both
undecided.**"* And CR038's own finding — prompt instructions are obeyed ~30% of the time — is the
proof that labelling was never going to be the control. We wrote that lesson down and then kept
labelling.

## The actual root cause is one function

`_profile_for_ticker` (`backend/app/services/room_runner.py:325-373`) builds a **complete fake
company** before any live fetch runs:

```python
rng = random.Random(zlib.crc32(ticker.upper().encode()))
base_price = 50 + rng.uniform(0, 400)
pe         = rng.uniform(12, 55)
rev_growth = rng.randint(2, 40)
profit_margin = rng.randint(8, 35)
… "net_cash": rng.randint(-5_000, 80_000), "rsi": rng.randint(35, 75), …
```

then overlays whatever live data it can get **on top of it** (`:376-405`) with `dict.update` — a
partial merge that leaves every unsupplied key at its rng value — and flips `data_source` to
`"yfinance_live"` for the whole profile.

**A loaded gun sitting in the production path, pointed at the prompt.** As long as those values
exist, every future gap in any provider silently reloads it. That is the entire mechanism-B class,
in one function.

**The blast radius is genuinely this small.** Swept `backend/app/` for `random.`/`rng.`/`Random(`:
the only fabricated *facts* are these lines. Everything else is legitimate — league handle
generation, retry jitter, and `market_data.py`'s explicitly-labelled mock price walk (which is a
declared simulation mode, not a disguised one).

## The change

**In production, a numeric fact is live or it is absent. There is no third state.**

1. **Delete the synthetic numeric fields from the production profile.** `_profile_for_ticker`
   returns only what a provider actually supplied. Narrative scaffolding that is honestly labelled
   illustrative (the CR034 sentiment convention) is a separate question — this CR is about numbers
   that masquerade as measurements.
2. **Move the deterministic baseline to a test fixture.** Reproducible unit tests were the real
   reason it exists (DEF057 even hardened its determinism). That requirement is fully served by a
   fixture the tests import; it does not need to ship.
3. **Provenance per field, not per block.** Each numeric carries its source; `_format_profile`
   renders a line only for fields that have one, and the disclosure header is then true by
   construction rather than by assertion. This is the same rendering change DEF123 needs and the
   same one CR098 Amendment 1 needs — do it once, here.
4. **Say "unavailable" out loud.** Every analyst prompt already instructs the agent to do this
   (*"If a fact you need is absent, say it is unavailable or omit the claim"*). They have never been
   given the chance, because the gap was always pre-filled.

## The guard — without this, this CR is instance 14

Per the house rule (second occurrence ⇒ an entry **with a guard**), and P2 currently has none:

- **A test that fails the build if any rng-derived numeric can reach `_format_profile`** under
  production config. Not a test of one field — a test of the invariant.
- **A renderer-level refusal:** a field with no provenance is not rendered. Structural, so a future
  provider gap degrades to a missing line instead of a fabricated one.
- **Re-run DEF123's measurement as an acceptance check** — the 178-of-842 count must be 0, and stay
  0. This is the corpus-level check P2 has been missing; CR037/CR038's undecided guards can bind to
  the same harness.
- **Update `failure_patterns.md` P2** with DEF123 as the instance that proves labelling failed, and
  name this guard as P2's enforcing check.

## What this costs, honestly

- **Yahoo outage → a thinner Room.** Today an outage produces a confident fake analysis; after
  this it produces a Room that says what it doesn't know. That is the stated CR040 invariant
  (*degrade loudly, never confidently*), not a regression — but it **will** look like one the first
  time it happens, and the client should render it as an intentional state.
- **Some tickers get a much thinner fact sheet.** Loss-making names lose the P/E line; ETFs lose
  the company-fundamentals block entirely. Correct, and less than we show today — the difference is
  that what remains is true.
- **It touches `_format_profile`, which CR098 also touches.** Sequence: **CR104 → DEF123 folds into
  it → CR098 rebases on top.** CR098's fact-sheet stripping becomes nearly free once provenance is
  per-field: a withheld analyst is just another field with no source.

## Scope note

This is **not** a rewrite of the Room. It is one function deleted, one renderer made
provenance-aware, one fixture moved to tests, and one guard added. The reason to do it as a CR
rather than inside DEF123 is that the *decision* — "we no longer ship fabricated numbers, even as
fallback" — is a product decision with a visible consequence, and it should be recorded as one.

## Governance

- Commit tag `(AT:R59 CR104)`. Status `proposed` — Saiful confirms the tradeoff above before it
  lanes, because the outage behaviour changes.
- **Independent audit recommended** (track R + track U): it changes what every agent is told is
  true, upstream of the safety floor's inputs.
- Relates to **DEF123** (its instance fix folds in here), **CR098** (rebases on top),
  **CR038** / **CR037** (the undecided guards can bind to CR104's acceptance check),
  **DEF052** / **DEF063** (earlier mechanism-B instances), **CR040** (degrade loudly),
  **CR046** (the mechanism-A ledger this mirrors for mechanism B), **DEF057** (determinism of the
  baseline being moved).
